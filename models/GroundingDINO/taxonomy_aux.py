"""Training-only projections and deduplicated text plan. BERT belongs to CountGD."""
import math
import random

import torch
from torch import nn


class TaxonomyAux(nn.Module):
    def __init__(self, query_dim, text_dim, registry, args):
        super().__init__()
        self.registry = registry
        self.use_contrast = args.use_level_contrast
        self.use_entailment = args.use_taxonomy_entailment
        self.geometry = args.entailment_geometry
        if self.geometry not in ('lorentz', 'euclidean_cones'):
            raise ValueError(f'Unknown entailment geometry: {self.geometry}')
        self.max_instances = args.aux_max_instances
        self.negatives = args.negatives_per_level
        self.chunk_size = args.aux_text_chunk_size
        self.min_radius = args.cone_min_radius
        self.bridge_weight = args.bridge_weight
        self.entailment_negatives = args.entailment_negatives_per_edge
        self.negative_margin = args.entailment_negative_margin
        self.negative_weight = args.entailment_negative_weight
        self.radial_margin = args.cone_radial_margin
        d = args.aux_embed_dim
        self.query_proj = nn.Sequential(nn.Linear(query_dim, query_dim), nn.GELU(), nn.Linear(query_dim, d))
        self.text_proj = nn.Sequential(nn.Linear(text_dim, text_dim), nn.GELU(), nn.Linear(text_dim, d))
        if args.temperature <= 0 or self.chunk_size < 1 or self.max_instances < 1 or self.negatives < 0:
            raise ValueError('Invalid auxiliary sampling/temperature settings')
        self.register_buffer('temperature', torch.tensor(args.temperature))
        if self.use_entailment:
            if (self.entailment_negatives < 1 or self.negative_margin <= 0
                    or self.negative_weight <= 0 or not 0 < self.min_radius < 1
                    or not 0 < self.radial_margin < 1):
                raise ValueError('Entailment needs negative parents, positive margin/weight and a valid cone radius')
            self.log_alpha_v = nn.Parameter(torch.tensor(-.5 * math.log(d)))
            self.log_alpha_t = nn.Parameter(torch.tensor(-.5 * math.log(d)))
            if not .1 <= args.curvature_init <= 10:
                raise ValueError('curvature_init must be in [0.1, 10]')
            if args.learn_curvature and self.geometry == 'lorentz':
                self.log_c = nn.Parameter(torch.tensor(math.log(args.curvature_init)))
            else:
                self.register_buffer('log_c', torch.tensor(math.log(args.curvature_init)))

    def plan(self, targets):
        reg = self.registry
        candidates = []
        for l in range(7):
            positive = {int(t['taxonomy_uids'][l]) for t in targets
                        if bool(t['taxonomy_valid_mask'][l]) and int(t['taxonomy_uids'][l]) in reg.train_nodes[l]}
            if self.use_contrast and positive:
                pool = sorted(reg.train_nodes[l] - positive)
                positive.update(random.sample(pool, min(self.negatives, len(pool))))
            candidates.append(sorted(positive))
        nodes = set(u for rank in candidates for u in rank)
        if self.use_entailment:
            # Add the unique ancestors of both positive paths and sampled candidates.
            for u in list(nodes):
                while u in reg.parent:
                    u = reg.parent[u]
                    nodes.add(u)
        # Freeze the positive-edge set before adding negative/diagnostic nodes.
        edges = sorted((p, c) for p, c in reg.train_edges if p in nodes and c in nodes) if self.use_entailment else []
        negative_edges = []
        diagnostic_candidates = [list(rank) for rank in candidates]
        if self.use_entailment:
            for parent, child in edges:
                rank = reg.nodes[parent]['rank']
                ancestors = set()
                ancestor = child
                while ancestor in reg.parent:
                    ancestor = reg.parent[ancestor]
                    ancestors.add(ancestor)
                # Only train nodes in the immediately preceding rank; no true ancestor.
                pool = sorted(reg.train_nodes[rank] - ancestors)
                # Prefer hard sibling parents, then fill from the same rank.
                grandparent = reg.parent.get(parent)
                siblings = [u for u in pool if reg.parent.get(u) == grandparent]
                chosen = random.sample(siblings, min(self.entailment_negatives, len(siblings)))
                rest = sorted(set(pool) - set(chosen))
                chosen += random.sample(rest, min(self.entailment_negatives - len(chosen), len(rest)))
                negative_edges.extend((wrong_parent, child) for wrong_parent in sorted(chosen))
                nodes.update(chosen)
            # Wrong-category query diagnostics also work in entailment-only / batch=1.
            # These comparisons are detached diagnostics, not an extra TV training loss.
            for rank in range(7):
                present = set(candidates[rank])
                if present:
                    pool = sorted(reg.train_nodes[rank] - present)
                    present.update(random.sample(pool, min(self.entailment_negatives, len(pool))))
                diagnostic_candidates[rank] = sorted(present)
                nodes.update(present)
        units = sorted({(t['species'], t['organ']) for t in targets
                        if (t['species'], t['organ']) in reg.train_units}) if self.use_entailment else []
        nodes = sorted(nodes)
        texts = [reg.nodes[u]['text'] for u in nodes] + [f'{organ} belonging to {species}.' for species, organ in units]
        return nodes, candidates, edges, negative_edges, diagnostic_candidates, units, texts

    def forward(self, queries, targets, encode_text):
        nodes, candidates, edges, negative_edges, diagnostic_candidates, units, texts = self.plan(targets)
        raw_q = self.query_proj(queries)
        if texts:
            # No cross-step hidden-state cache: feat_map and projections remain trainable.
            raw_t = self.text_proj(encode_text(texts, self.chunk_size))
        else:
            raw_t = raw_q.new_empty((0, raw_q.shape[-1]))
        # Always touch auxiliary trainable parameters, including on a rank with no valid paths.
        zero = raw_q.float().sum() * 0 + sum(p.sum() * 0 for p in self.parameters())
        result = {'queries': raw_q, 'texts': raw_t, 'zero': zero,
                  'node_index': {u: i for i, u in enumerate(nodes)},
                  'unit_index': {unit: len(nodes) + i for i, unit in enumerate(units)},
                  'candidates': candidates, 'edges': edges, 'negative_edges': negative_edges,
                  'diagnostic_candidates': diagnostic_candidates, 'registry': self.registry,
                  'use_contrast': self.use_contrast, 'use_entailment': self.use_entailment,
                  'geometry': self.geometry, 'max_instances': self.max_instances,
                  'temperature': self.temperature, 'min_radius': self.min_radius,
                  'bridge_weight': self.bridge_weight, 'negative_margin': self.negative_margin,
                  'negative_weight': self.negative_weight, 'radial_margin': self.radial_margin}
        if self.use_entailment:
            result.update({'alpha_v': self.log_alpha_v.clamp(-9.21, 0).exp(),
                           'alpha_t': self.log_alpha_t.clamp(-9.21, 0).exp(),
                           'curvature': self.log_c.clamp(math.log(.1), math.log(10)).exp()})
        return result


if __name__ == '__main__':
    import argparse
    from types import SimpleNamespace
    from datasets.tpc268 import TPC268Dataset
    from datasets.tpc268_taxonomy import registry_from_args
    from util.slconfig import SLConfig
    from .groundingdino import SetCriterion
    from .matcher import build_matcher

    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-check', action='store_true')
    parser.add_argument('--config', default='config/cfg_tpc268_full.py')
    cli = parser.parse_args()
    if cli.smoke_check:
        # Real annotation metadata + synthetic features. This exercises criterion
        # alignment/projection gradients, NOT CountGD/BERT inference or counting quality.
        args = SimpleNamespace(**SLConfig.fromfile(cli.config)._cfg_dict.to_dict())
        random.seed(42)
        torch.manual_seed(42)
        reg = registry_from_args(args)
        ds = TPC268Dataset(args, 'train', reg)
        resolved = [i for i, p in enumerate(ds.paths) if reg.resolve(p.split('/')[0])]
        first = resolved[0]
        second = next(i for i in resolved if ds.paths[i].split('/')[0] != ds.paths[first].split('/')[0])
        targets = [ds[i][1] for i in (first, first, second)]
        hidden_dim, num_queries = 24, max(len(t['boxes']) for t in targets) + 4
        aux = TaxonomyAux(hidden_dim, hidden_dim, reg, args)
        # Lightweight differentiable text-feature stand-in; no external weights.
        text_encoder = nn.Linear(hidden_dim, hidden_dim)

        def encode(texts, chunk):
            input_features = torch.randn(len(texts), hidden_dim)
            return text_encoder(input_features)

        queries = torch.randn(3, num_queries, hidden_dim, requires_grad=True)
        auxiliary = aux(queries, targets, encode)
        for parent, child in auxiliary['negative_edges']:
            assert parent in reg.train_nodes[reg.nodes[child]['rank'] - 1]
            current = child
            while current in reg.parent:
                current = reg.parent[current]
                assert parent != current, 'False negative ancestor'
        if args.use_taxonomy_entailment:
            assert auxiliary['negative_edges'], 'Real train taxonomy should supply wrong parents'
        logits = torch.randn(3, num_queries, 256, requires_grad=True)
        boxes = torch.rand(3, num_queries, 4, requires_grad=True)
        # [CLS], one target word, period, [SEP] represents a single count phrase.
        token = {'input_ids': torch.tensor([[101, 2000, 1012, 102]] * 3)}
        outputs = {'pred_logits': logits, 'pred_boxes': boxes, 'token': token,
                   'text_mask': torch.zeros(3, 256, dtype=torch.bool), 'taxonomy_aux': auxiliary}
        outputs['text_mask'][:, :4] = True
        outputs['aux_outputs'] = [{'pred_logits': logits.flip(1), 'pred_boxes': boxes.flip(1)}]
        weight = {'loss_ce': 5., 'loss_bbox': 1., 'loss_giou': 0.}
        criterion = SetCriterion(build_matcher(args), weight, args.focal_alpha, args.focal_gamma, ['labels', 'boxes'])
        losses, indices = criterion(outputs, targets, [t['cap_list'] for t in targets],
                                    [t['caption'] for t in targets], return_indices=True)
        from .taxonomy_losses import taxonomy_losses
        direct = taxonomy_losses(auxiliary, targets, indices[-1])
        active_keys = (["loss_level_contrast"] if args.use_level_contrast else [])
        active_keys += (["loss_entail_tt", "loss_entail_tv"] if args.use_taxonomy_entailment else [])
        # max_instances >= these counts, so stochastic subsampling is unnecessary.
        if max(len(t['boxes']) for t in targets) <= args.aux_max_instances:
            for key in active_keys:
                assert torch.allclose(losses[key], direct[key]), key
        total = sum(losses[k] for k in active_keys)
        assert torch.isfinite(total)
        total.backward()
        assert queries.grad is not None and torch.isfinite(queries.grad).all() and queries.grad.abs().sum() > 0
        for b, (src, _) in enumerate(indices[-1]):
            unmatched = torch.ones(num_queries, dtype=torch.bool)
            unmatched[src] = False
            assert queries.grad[b, unmatched].abs().sum() == 0
        for name, p in aux.named_parameters():
            assert p.grad is not None and torch.isfinite(p.grad).all(), name
        assert text_encoder.weight.grad.abs().sum() > 0
        if args.use_taxonomy_entailment:
            assert float(losses['tax_aperture_invalid_rate']) == 0
            assert any(float(losses[f'tax_tt_rank_{rank}_negative_pairs']) > 0 for rank in range(6))
        # No valid taxonomy / no matches: losses must still connect all heads.
        aux.zero_grad(set_to_none=True)
        empty_targets = [dict(t, taxonomy_valid_mask=torch.zeros(7, dtype=torch.bool)) for t in targets]
        empty = aux(queries.detach(), empty_targets, encode)
        zero = taxonomy_losses(empty, empty_targets,
                               [(torch.empty(0, dtype=torch.long), torch.empty(0, dtype=torch.long))] * 3)
        sum(zero[k] for k in active_keys).backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in aux.parameters())
        print('Real-metadata criterion smoke passed: final matching, train-only non-ancestor negatives, valid cones, rank diagnostics, head/text/query gradients, unmatched-query exclusion, empty-path graph')
