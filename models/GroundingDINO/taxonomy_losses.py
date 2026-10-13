"""Final Hungarian-query supervision, image/rank-balanced and parameter-free."""
import torch
import torch.nn.functional as F

from . import lorentz as L


def image_mean(values, image_ids, zero):
    means = [values[image_ids == i].mean() for i in image_ids.unique()]
    return torch.stack(means).mean() if means else zero


def cone_geometry(parent, child, c, geometry, min_radius):
    if geometry == 'lorentz':
        aperture = L.half_aperture(parent, c, min_radius, eps=1e-6)
        angle = L.oxy_angle(parent, child, c, eps=1e-6)
        radius = torch.asinh(c.sqrt() * parent.norm(dim=-1)) / c.sqrt()
        invalid = c.sqrt() * parent.norm(dim=-1) < 2 * min_radius
    else:
        # Ganea et al. 2018, Euclidean cones: psi=asin(K/||x||),
        # Xi=acos(<x,y-x>/(||x|| ||y-x||)). Here K=min_radius.
        norm = parent.norm(dim=-1)
        delta = child - parent
        cosine = (parent * delta).sum(-1) / (norm * delta.norm(dim=-1)).clamp_min(1e-6)
        angle = torch.acos(cosine.clamp(-1 + 1e-6, 1 - 1e-6))
        aperture = torch.asin((min_radius / norm.clamp_min(1e-6)).clamp(max=1 - 1e-6))
        radius = norm
        invalid = norm < min_radius
    if invalid.any():
        raise ValueError('Entailment parent outside cone domain; use geometry_map before cone_geometry')
    return angle, aperture, radius, invalid.float()


def cone_energy(parent, child, c, geometry, min_radius):
    angle, aperture, radius, invalid = cone_geometry(parent, child, c, geometry, min_radius)
    return F.relu(angle - aperture), aperture, radius, invalid.float()


def negative_cone_energy(parent, child, c, geometry, min_radius, margin):
    # SEL negative entailment: an unrelated preceding-rank node must NOT contain child.
    # https://arxiv.org/html/2508.16744v1, Eq. (2). margin is in radians.
    angle, aperture, _, _ = cone_geometry(parent, child, c, geometry, min_radius)
    return F.relu(aperture - angle + margin)


def geometry_map(raw, alpha, c, geometry, min_radius=.1, radial_margin=.05):
    """Preserve direction/radial freedom while mapping every node outside the cone hole.

    Lorentz space norm must exceed 2K/sqrt(c), so its tangent radius must exceed
    asinh(2K)/sqrt(c). Euclidean cones require radius > K. The positive radial
    offset is differentiable; unlike a lower clamp, it retains radial gradients.
    An exactly/near-zero direction uses a fixed axis, never a fabricated taxonomy.
    """
    tangent = raw * alpha
    norm = tangent.norm(dim=-1, keepdim=True)
    threshold = tangent.new_tensor(min_radius * (1 + radial_margin))
    floor = torch.asinh(2 * threshold) / c.sqrt() if geometry == 'lorentz' else threshold
    bound = 4 / c.sqrt() if geometry == 'lorentz' else tangent.new_tensor(4.)
    radius = floor + norm
    saturated = (radius.squeeze(-1) > bound).float()
    direction = tangent / norm.clamp_min(1e-6)
    fallback = torch.zeros_like(tangent)
    fallback[..., 0] = 1
    direction = torch.where(norm > 1e-6, direction, fallback)
    # Upper guard limits float32 Lorentz cancellation as well as sinh.
    tangent = direction * torch.minimum(radius, bound)
    return (L.exp_map0(tangent, c) if geometry == 'lorentz' else tangent), saturated


def record_cone_stats(result, prefix, parent, child, c, aux, zero, image_ids=None,
                      negative=False, details=False):
    """Detached diagnostics: no extra ancestor/query supervision is added here."""
    with torch.no_grad():
        angle, aperture, radius, invalid = cone_geometry(
            parent.detach(), child.detach(), c.detach(), aux['geometry'], aux['min_radius'])
        mean = lambda value: (image_mean(value, image_ids, zero.detach()) if image_ids is not None
                              else value.mean() if value.numel() else zero.detach())
        result[prefix + '_pairs'] = zero.detach() + angle.numel()
        result[prefix + '_inclusion_rate'] = mean((angle <= aperture).float())
        if negative:
            result[prefix + '_margin_violation_rate'] = mean((angle < aperture + aux['negative_margin']).float())
        if details:
            result[prefix + '_aperture'] = mean(aperture)
            result[prefix + '_parent_radius'] = mean(radius)
            result[prefix + '_invalid_rate'] = mean(invalid)
            if aux['geometry'] == 'lorentz':
                child_radius = torch.asinh(c.sqrt() * child.detach().norm(dim=-1)) / c.sqrt()
            else:
                child_radius = child.detach().norm(dim=-1)
            result[prefix + '_outward_rate'] = mean((child_radius > radius).float())


def taxonomy_losses(aux, targets, final_indices):
    device = aux['queries'].device
    # Explicitly disable autocast for all geometry, similarity and projections' outputs.
    with torch.autocast(device_type=device.type, enabled=False):
        q, text, zero = aux['queries'].float(), aux['texts'].float(), aux['zero'].float()
        selected, images, paths, valid, unit_indices = [], [], [], [], []
        reg = aux['registry']
        for b, (src, tgt) in enumerate(final_indices):
            if len(src) > aux['max_instances']:
                keep = torch.randperm(len(src), device=src.device)[:aux['max_instances']]
                src, tgt = src[keep], tgt[keep]
            if not len(src):
                continue
            # Use tgt_idx, even though TPC's per-image metadata are shared by all GTs.
            target = targets[b]
            gt_paths = target['taxonomy_uids'].expand(len(target['boxes']), -1)
            gt_valid = target['taxonomy_valid_mask'].expand(len(target['boxes']), -1)
            p = gt_paths[tgt.to(gt_paths.device)]
            mask = gt_valid[tgt.to(gt_valid.device)].clone()
            for l in range(7):
                mask[:, l] &= torch.tensor([int(u) in reg.train_nodes[l] for u in p[:, l]], device=device)
            selected.append(q[b, src.to(device)])
            images.append(torch.full((len(src),), b, device=device, dtype=torch.long))
            paths.append(p)
            valid.append(mask)
            unit_indices.extend([aux['unit_index'].get((target['species'], target['organ']), -1)] * len(src))
        if selected:
            visual = torch.cat(selected)
            image_ids = torch.cat(images)
            path_ids, valid_mask = torch.cat(paths), torch.cat(valid)
        else:
            visual = q.reshape(-1, q.shape[-1])[:0]
            image_ids = torch.empty(0, device=device, dtype=torch.long)
            path_ids = torch.empty((0, 7), device=device, dtype=torch.long)
            valid_mask = torch.empty((0, 7), device=device, dtype=torch.bool)
        result = {}
        rank_losses = []
        for l in range(7):
            z = zero
            candidates = aux['candidates'][l]
            mask = valid_mask[:, l]
            labels = path_ids[mask, l]
            ids = image_ids[mask]
            if aux['use_contrast'] and len(labels) and len(candidates) > 1:
                candidate_rows = [aux['node_index'][u] for u in candidates]
                v = F.normalize(visual[mask], dim=-1)
                t = F.normalize(text[candidate_rows], dim=-1)
                scores = v @ t.T / aux['temperature'].float()
                y = torch.tensor([candidates.index(int(u)) for u in labels], device=device)
                vt = image_mean(F.cross_entropy(scores, y, reduction='none'), ids, zero)
                # Each text anchor has ALL matching queries as positives, grouped by image.
                if y.unique().numel() >= 2:
                    log_probs = scores.log_softmax(dim=0)
                    tv = torch.stack([image_mean(-log_probs[y == k, k], ids[y == k], zero)
                                      for k in y.unique()]).mean()
                    z = .5 * (vt + tv)
                else:
                    z = vt
                rank_losses.append(z)
            elif aux['use_contrast'] and len(labels):
                rank_losses.append(z)
            if aux['use_contrast']:
                result[f'tax_rank_{l}_loss'] = z.detach()
                result[f'tax_rank_{l}_candidates'] = zero.detach() + len(candidates)
                result[f'tax_rank_{l}_positives'] = zero.detach() + len(labels)
        if aux['use_contrast']:
            result['loss_level_contrast'] = (torch.stack(rank_losses).mean() if rank_losses else zero) + zero
        if aux['use_entailment']:
            c = aux['curvature'].float()
            mapping = (c, aux['geometry'], aux['min_radius'], aux['radial_margin'])
            ht, sat_t = geometry_map(text, aux['alpha_t'].float(), *mapping)
            hv, sat_v = geometry_map(visual, aux['alpha_v'].float(), *mapping)
            energies, apertures, radii, invalids = [], [], [], []

            def relation(p, child):
                e, aperture, radius, invalid = cone_energy(p, child, c, aux['geometry'], aux['min_radius'])
                energies.append(e)
                apertures.append(aperture)
                radii.append(radius)
                invalids.append(invalid)
                return e

            def edge_features(edges):
                parents = torch.tensor([aux['node_index'][p] for p, _ in edges], device=device, dtype=torch.long)
                children = torch.tensor([aux['node_index'][child] for _, child in edges], device=device, dtype=torch.long)
                return ht[parents], ht[children]

            positive_means, negative_means = [], []
            for rank in range(6):
                positive_edges = [(p, child) for p, child in aux['edges'] if reg.nodes[p]['rank'] == rank]
                negative_edges = [(p, child) for p, child in aux['negative_edges'] if reg.nodes[p]['rank'] == rank]
                parent, child = edge_features(positive_edges)
                positive = relation(parent, child)
                wrong_parent, neg_child = edge_features(negative_edges)
                negative = negative_cone_energy(wrong_parent, neg_child, c, aux['geometry'],
                                                aux['min_radius'], aux['negative_margin'])
                # Average negatives per child, then per rank; candidate count is not a weight.
                child_ids = torch.tensor([child_id for _, child_id in negative_edges], device=device, dtype=torch.long)
                pos_mean = positive.mean() if positive.numel() else zero
                neg_mean = image_mean(negative, child_ids, zero)
                if positive_edges:
                    positive_means.append(pos_mean)
                    negative_means.append(neg_mean)
                prefix = f'tax_tt_rank_{rank}'
                result[prefix + '_positive_loss'] = pos_mean.detach()
                result[prefix + '_negative_loss'] = neg_mean.detach()
                record_cone_stats(result, prefix + '_positive', parent, child, c, aux, zero, details=True)
                record_cone_stats(result, prefix + '_negative', wrong_parent, neg_child, c, aux, zero, negative=True)
            tt_positive = torch.stack(positive_means).mean() if positive_means else zero
            tt_negative = torch.stack(negative_means).mean() if negative_means else zero
            # Keep the old positive scale, adding separately configurable negative pressure.
            tt = tt_positive + aux['negative_weight'] * tt_negative
            result['tax_tt_positive_loss'] = tt_positive.detach()
            result['tax_tt_negative_loss'] = tt_negative.detach()
            bridge_edges = []
            for (species, _), row in aux['unit_index'].items():
                species_row = aux['node_index'].get(reg.paths[species][-1])
                if species_row is not None:
                    bridge_edges.append((species_row, row))
            bridge_parent = ht[[p for p, _ in bridge_edges]]
            bridge_child = ht[[child for _, child in bridge_edges]]
            bridges = relation(bridge_parent, bridge_child)
            bridge = bridges.mean() if bridges.numel() else zero
            # This is a task bridge, deliberately not logged as an eighth taxonomy rank.
            record_cone_stats(result, 'tax_unit_bridge', bridge_parent, bridge_child, c, aux, zero, details=True)
            result['loss_hyp_unit_bridge'] = bridge.detach()
            result['loss_entail_tt'] = tt + aux['bridge_weight'] * bridge + zero
            rows = torch.tensor(unit_indices, device=device, dtype=torch.long)
            mask = (rows >= 0) & valid_mask.all(dim=1)
            tv_parent, tv_child = ht[rows[mask]], hv[mask]
            tv_energy = relation(tv_parent, tv_child)
            result['loss_entail_tv'] = image_mean(tv_energy, image_ids[mask], zero) + zero
            record_cone_stats(result, 'tax_unit_query', tv_parent, tv_child, c, aux, zero,
                              image_ids[mask], details=True)
            # Each matched query is compared with its correct ancestor and unrelated
            # SAME-rank train nodes for monitoring only. No extra loss or query gather.
            with torch.no_grad():
                for rank in range(7):
                    rank_mask = valid_mask[:, rank]
                    label_uids = path_ids[rank_mask, rank]
                    correct_rows = torch.tensor([aux['node_index'][int(u)] for u in label_uids],
                                                device=device, dtype=torch.long)
                    rank_visual, ids = hv[rank_mask], image_ids[rank_mask]
                    prefix = f'tax_query_rank_{rank}'
                    record_cone_stats(result, prefix + '_positive', ht[correct_rows], rank_visual,
                                      c, aux, zero, ids)
                    candidates = aux['diagnostic_candidates'][rank]
                    pair_mask = label_uids[:, None] != torch.tensor(candidates, device=device, dtype=torch.long)[None, :]
                    query_idx, candidate_idx = pair_mask.nonzero(as_tuple=True)
                    candidate_rows = torch.tensor([aux['node_index'][u] for u in candidates],
                                                  device=device, dtype=torch.long)
                    record_cone_stats(result, prefix + '_negative', ht[candidate_rows[candidate_idx]],
                                      rank_visual[query_idx], c, aux, zero, ids[query_idx], negative=True)
            if any(e.numel() for e in energies):
                result['tax_aperture'] = torch.cat(apertures).mean().detach()
                result['tax_parent_radius'] = torch.cat(radii).mean().detach()
                result['tax_violation_rate'] = (torch.cat(energies) > 0).float().mean().detach()
                result['tax_aperture_invalid_rate'] = torch.cat(invalids).mean().detach()
            else:
                for key in ('tax_aperture', 'tax_parent_radius', 'tax_violation_rate', 'tax_aperture_invalid_rate'):
                    result[key] = zero.detach()
            saturation = torch.cat([sat_t, sat_v])
            result['tax_tangent_saturated_rate'] = saturation.mean().detach() if len(saturation) else zero.detach()
            result['tax_curvature'] = c.detach()
        return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-check', action='store_true')
    cli = parser.parse_args()
    if cli.smoke_check:
        for geometry in ('lorentz', 'euclidean_cones'):
            torch.manual_seed(42)
            raw = torch.randn(8, 128, requires_grad=True)
            child = torch.randn(8, 128, requires_grad=True)
            log_c = torch.tensor(0., requires_grad=True)
            alpha = torch.tensor(-2., requires_grad=True)
            c = log_c.exp()
            p, _ = geometry_map(raw, alpha.exp(), c, geometry)
            y, _ = geometry_map(child, alpha.exp(), c, geometry)
            energy, _, _, _ = cone_energy(p, y, c, geometry, .1)
            assert torch.isfinite(energy).all()
            energy.mean().backward()
            assert raw.grad is not None and torch.isfinite(raw.grad).all() and raw.grad.abs().sum() > 0
            assert child.grad is not None and torch.isfinite(child.grad).all()
            assert alpha.grad is not None and torch.isfinite(alpha.grad)
            if geometry == 'lorentz':
                assert log_c.grad is not None and torch.isfinite(log_c.grad)
            # The old same-ray collapse has zero positive loss, but positive negative loss.
            ray = torch.zeros(2, 128)
            ray[:, 0] = torch.tensor([.5, 1.])
            mapped, _ = geometry_map(ray, torch.tensor(1.), c.detach(), geometry)
            positive, _, _, invalid = cone_energy(mapped[:1], mapped[1:], c.detach(), geometry, .1)
            wrong = negative_cone_energy(mapped[:1], mapped[1:], c.detach(), geometry, .1, .1)
            assert positive.item() == 0 and not invalid.any() and wrong.item() > 0
            outside = negative_cone_energy(mapped[:1], -mapped[1:], c.detach(), geometry, .1, .1)
            assert outside.item() == 0
            for curvature in (.1, 1., 10.):
                tiny = torch.zeros(4, 128, requires_grad=True)
                tiny.data[1, 0] = 1e-8
                tiny.data[2, 0] = .01
                tiny.data[3, 0] = 100
                curved = torch.tensor(curvature, requires_grad=True)
                legal, saturation = geometry_map(tiny, torch.tensor(1.), curved, geometry)
                _, _, _, invalid = cone_energy(legal, legal, curved, geometry, .1)
                assert not invalid.any() and saturation[-1] == 1
                legal.sum().backward()
                assert torch.isfinite(tiny.grad).all()
                if geometry == 'lorentz':
                    assert curved.grad is not None and torch.isfinite(curved.grad)
            try:
                cone_energy(torch.zeros(1, 128), mapped[1:], c.detach(), geometry, .1)
            except ValueError:
                pass
            else:
                raise AssertionError('An illegal parent must not silently get a zero loss')
            print(geometry, 'finite gradients, valid zero/tiny/saturated maps, collapse rejected by negative loss passed')
