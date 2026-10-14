"""CountGD point adapter for TPC-268's official basename annotations.

Protocol adapted from https://github.com/tiny-smart/TPC-268/blob/main/tools/tpc268_dataset.py
(commit in data/tpc268_metadata/sources.json).
points/boxes: normalized xy / cxcywh after transform. Exemplars: transformed
pixel xyxy for roi_align. Pseudo box sizes carry points; only centers supervised.
Training reuses CountGD's resize/crop policy. Crop membership uses point centers;
exemplars are clipped and empty boxes removed, never duplicated.
"""
import json
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset

from .odvg import make_coco_transforms
from .tpc268_taxonomy import read_split, registry_from_args


def counting_phrase(registry, path, mode):
    species, organ, ids, _, valid = registry.metadata(path)
    if mode not in ('organ', 'species', 'full_taxonomy'):
        raise ValueError(f'Unknown prompt mode: {mode}')
    if mode == 'organ':
        # Caption control: taxonomy stays in training metadata, not model input.
        # The three visual exemplars identify which organ instances to count.
        return organ
    phrase = f'{organ} of {species}'
    if mode == 'full_taxonomy' and all(valid):
        names = [registry.reverse[l][int(i)] for l, i in enumerate(ids)]
        phrase += '; taxonomy: ' + ', '.join(names)
    return phrase


def annotation_coordinates(annotation, size, path):
    """Validate point labels; intersect exemplar ROIs with the image canvas.

    Do not infer resize/rotation from out-of-bounds points or discard labels.
    Return changed boxes so the full audit records every boundary correction.
    """
    w, h = size
    points = torch.tensor(annotation['points'], dtype=torch.float32).reshape(-1, 2)
    polygons = torch.tensor(annotation['box_examples_coordinates'], dtype=torch.float32).reshape(-1, 4, 2)
    boxes = torch.cat([polygons.amin(1), polygons.amax(1)], dim=1)
    if len(boxes) != 3 or not torch.all(boxes[:, 2:] > boxes[:, :2]):
        raise ValueError(f'{path}: need exactly three valid exemplar boxes, received {len(boxes)}')
    if not torch.isfinite(points).all() or not torch.isfinite(polygons).all():
        raise ValueError(f'{path}: nonfinite coordinates')
    outside = ((points < 0) | (points > torch.tensor([w, h]))).any(dim=1)
    if outside.any():
        raise ValueError(f'{path}: {int(outside.sum())} points outside original image '
                         f'{w}x{h}; verify original image size/orientation against annotations')
    clipped = torch.minimum(boxes.clamp(min=0), boxes.new_tensor([w, h, w, h]))
    if not torch.all(clipped[:, 2:] > clipped[:, :2]):
        raise ValueError(f'{path}: exemplar has no positive-area intersection with image')
    changes = [{'index': i, 'original': boxes[i].tolist(), 'clipped': clipped[i].tolist()}
               for i in range(3) if not torch.equal(boxes[i], clipped[i])]
    return points, clipped, changes


class TPC268Dataset(Dataset):
    def __init__(self, args, split, registry=None):
        self.args, self.split = args, split
        self.root = Path(args.tpc268_root)
        original_paths = read_split(getattr(args, f'tpc268_{split}_split'))
        excluded = set(getattr(args, 'tpc268_excluded_paths', []))
        self.excluded_paths = sorted(set(original_paths) & excluded)
        self.paths = [p for p in original_paths if p not in excluded]
        print(f'TPC-268 {split} excluded: {self.excluded_paths}')
        self.registry = registry or registry_from_args(args)
        self.transforms = make_coco_transforms(split, getattr(args, 'fix_size', False), False, args)
        self.annotations = json.loads(Path(args.tpc268_annotation_file).read_text())
        self.taxonomy_report = self.registry.report(self.paths)
        print(f'TPC-268 {split} taxonomy: {self.taxonomy_report}')
        if args.strict_taxonomy and self.taxonomy_report['unresolved_species']:
            raise ValueError(f'Unresolved taxonomy: {self.taxonomy_report["unresolved_species"]}')
        if args.num_exemplars != 3:
            raise ValueError('TPC-268 protocol requires exactly three original exemplars')
        split_json = json.loads(Path(args.tpc268_split_json).read_text())
        expected = set(split_json[split])
        actual = {p.split('/')[0] + '_' + p.split('/')[1] for p in self.paths}
        if actual != expected:
            raise ValueError(f'{split} txt/category JSON mismatch: {actual ^ expected}')
        self.counts = []
        for p in self.paths:
            if Path(p).name not in self.annotations:
                raise KeyError(f'Missing annotation for {p}')
            self.counts.append(len(self.annotations[Path(p).name]['points']))
        counts = torch.tensor(self.counts, dtype=torch.float32)
        self.count_report = {'max': int(counts.max()) if len(counts) else 0,
                             'over_query_limit': int((counts > args.num_queries).sum()),
                             'quantiles': torch.quantile(counts, torch.tensor([0., .5, .9, .99, 1.])).tolist()}
        print(f'TPC-268 {split} count distribution: {self.count_report}; query limit={args.num_queries}')

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        p = self.paths[index]
        with Image.open(self.root / p) as source:
            image = source.convert('RGB')
        w, h = image.size
        annotation = self.annotations[Path(p).name]
        points, exemplars, _ = annotation_coordinates(annotation, (w, h), p)
        # Pixel xyxy carriers before the shared transforms; final Normalize converts
        # them to cxcywh. point_supervision keeps centers exact during cropping.
        half_size = self.args.point_box_size_px / 2
        boxes = torch.cat([points - half_size, points + half_size], dim=1)
        species, organ, ids, uids, valid = self.registry.metadata(p)
        phrase = counting_phrase(self.registry, p, self.args.prompt_mode)
        # Unresolved images keep species text and count training, with no auxiliary supervision.
        target = {'point_supervision': True, 'points': points, 'boxes': boxes,
                  'area': torch.full((len(points),), self.args.point_box_size_px ** 2),
                  'labels': torch.zeros(len(points), dtype=torch.long),
                  'labels_uncropped': torch.tensor([0]), 'exemplars': exemplars,
                  'caption': phrase + ' .', 'cap_list': [phrase], 'image_id': torch.tensor(index),
                  'relative_path': p, 'species_original': p.split('/')[0], 'species': species,
                  'organ': organ, 'split': self.split, 'orig_size': torch.tensor([h, w]),
                  'size': torch.tensor([h, w]), 'taxonomy_ids': torch.tensor(ids),
                  'taxonomy_uids': torch.tensor(uids), 'taxonomy_valid_mask': torch.tensor(valid),
                  'organ_id': torch.tensor(self.registry.organs.index(organ) if organ in self.registry.organs else -1),
                  'count': torch.tensor(len(points)), 'orig_count': torch.tensor(len(points))}
        image, target = self.transforms(image, target)
        target['count'] = torch.tensor(len(target['points']))
        return image, target


def build(image_set, args, datasetinfo):
    return TPC268Dataset(args, datasetinfo.get('split', image_set), getattr(args, 'taxonomy_registry', None))


if __name__ == '__main__':
    import argparse
    from types import SimpleNamespace
    from util.slconfig import SLConfig
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--crop-smoke-check', action='store_true')
    parser.add_argument('--config', default='config/cfg_tpc268_full.py')
    parser.add_argument('--root')
    parser.add_argument('--tokenizer', help='Optional local BERT tokenizer; offline audit of all prompts/prefixes')
    parser.add_argument('--output', default='docs/tpc268_data_audit.json')
    cli = parser.parse_args()
    if cli.audit:
        args = SimpleNamespace(**SLConfig.fromfile(cli.config)._cfg_dict.to_dict())
        if cli.root:
            args.tpc268_root = cli.root
        report = {}
        all_paths = set()
        unresolved = {}
        coordinate_errors = []
        for split in ('train', 'val', 'test'):
            ds = TPC268Dataset(args, split)
            if all_paths.intersection(ds.paths):
                raise ValueError('Official split image overlap')
            all_paths.update(ds.paths)
            missing = [p for p in ds.paths if not (ds.root / p).is_file()]
            report[split] = {**ds.taxonomy_report, 'counts': ds.count_report, 'species_organ_units': len({tuple(p.split('/')[:2]) for p in ds.paths}), 'missing_images': missing, 'excluded_paths': ds.excluded_paths}
            unresolved[split] = ds.taxonomy_report['unresolved_species']
            corrections, errors = [], []
            missing_set = set(missing)
            for p in ds.paths:
                if p in missing_set:
                    continue
                try:
                    with Image.open(ds.root / p) as source:
                        size = source.size
                    _, _, changes = annotation_coordinates(ds.annotations[Path(p).name], size, p)
                    if changes:
                        corrections.append({'path': p, 'size': list(size), 'boxes': changes})
                except (ValueError, RuntimeError, OSError, KeyError) as exc:
                    errors.append({'path': p, 'error': str(exc)})
            report[split]['coordinate_audit'] = {
                'checked_images': len(ds.paths) - len(missing),
                'clipped_exemplar_images': corrections, 'errors': errors}
            coordinate_errors.extend(errors)
            print(f'{split} coordinate audit: {len(corrections)} clipped exemplar images, {len(errors)} errors')
            if not missing and not errors:
                image, target = ds[0]
                assert target['exemplars'].shape[1] == 4
                assert 0 <= len(target['exemplars']) <= 3
                assert torch.allclose(target['boxes'][:, :2], target['points'])
                assert len(target['boxes']) == target['count'] <= target['orig_count']
                if split != 'train':
                    assert len(target['boxes']) == target['orig_count'] and len(target['exemplars']) == 3
                report[split]['sample_shape'] = list(image.shape)
                report[split]['sample_transformed_count'] = int(target['count'])
                report[split]['sample_exemplars'] = len(target['exemplars'])
        if cli.tokenizer:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(cli.tokenizer, local_files_only=True)
            token_report = {}
            for mode in ('organ', 'species', 'full_taxonomy'):
                captions = sorted({counting_phrase(ds.registry, p, mode) + ' .' for p in all_paths})
                lengths = []
                for caption in captions:
                    token = tokenizer(caption, return_offsets_mapping=True)
                    lengths.append(len(token['input_ids']) + args.num_exemplars)
                    if lengths[-1] > args.max_text_len:
                        raise ValueError(f'Truncated counting target: {caption}')
                    if token['input_ids'].count(1012) != 1:
                        raise ValueError(f'Counting caption is not a single target category: {caption}')
                    # Organ/species appear before the taxonomy suffix and remain tokenized.
                    prefix_end = caption.find(';') if ';' in caption else len(caption) - 2
                    if token.char_to_token(0) is None or token.char_to_token(prefix_end - 1) is None:
                        raise ValueError(f'Organ/species token span lost: {caption}')
                token_report[mode] = {'unique_captions': len(captions), 'max_tokens_including_exemplars': max(lengths)}
            prefixes = [node['text'] for node in ds.registry.nodes.values()]
            prefix_max = max(len(tokenizer(text)['input_ids']) for text in prefixes)
            assert prefix_max <= args.max_text_len
            token_report['taxonomy_prefix_max_tokens'] = prefix_max
            report['tokenizer_audit'] = token_report
            print(f'Tokenizer audit: {token_report}')
        Path(cli.output).write_text(json.dumps(report, indent=2))
        Path(cli.output).with_suffix('.unresolved_taxonomy.json').write_text(json.dumps(unresolved, indent=2))
        if coordinate_errors or any(report[s]['missing_images'] for s in ('train', 'val', 'test')):
            raise ValueError(f'Full dataset audit failed: {len(coordinate_errors)} coordinate errors; '
                             f'check missing_images and coordinate_audit in {cli.output}')
    if cli.crop_smoke_check:
        import random
        import datasets.transforms as T
        args = SimpleNamespace(**SLConfig.fromfile(cli.config)._cfg_dict.to_dict())
        if cli.root:
            args.tpc268_root = cli.root
        # Border centers distinguish correct point membership from carrier overlap.
        points = torch.tensor([[9.5, 30], [10, 20], [49.5, 40], [50, 40],
                               [30, 9.5], [30, 10], [30, 49.5], [30, 50]])
        raw = {'point_supervision': True, 'points': points,
               'boxes': torch.cat([points - 1, points + 1], dim=1),
               'labels': torch.arange(len(points)), 'area': torch.full((len(points),), 4.),
               'exemplars': torch.tensor([[12., 12, 18, 18], [0, 0, 5, 5], [48, 48, 60, 60]]),
               'labels_uncropped': torch.tensor([0])}
        image, cropped = T.crop(Image.new('RGB', (100, 80)), raw, (10, 10, 40, 40))
        assert cropped['labels'].tolist() == [1, 2, 5, 6]
        assert cropped['exemplars'].tolist() == [[2., 2., 8., 8.], [38., 38., 40., 40.]]
        image, normalized = T.Compose([T.ToTensor(), T.Normalize([0., 0., 0.], [1., 1., 1.])])(image, cropped)
        assert torch.allclose(normalized['boxes'][:, :2], normalized['points'])
        _, empty = T.crop(Image.new('RGB', (100, 80)), raw, (60, 60, 20, 20))
        assert empty['boxes'].shape == (0, 4) and empty['points'].shape == (0, 2)
        assert empty['exemplars'].shape == (0, 4) and empty['labels_uncropped'].tolist() == [0]
        # Same seeds and original construction must produce identical image/exemplar
        # transforms; only the GT filtering rule differs for point supervision.
        ds = TPC268Dataset(args, 'train')
        p = ds.paths[0]
        with Image.open(ds.root / p) as source:
            original = source.convert('RGB')
        annotation = ds.annotations[Path(p).name]
        pts = torch.tensor(annotation['points'], dtype=torch.float32).reshape(-1, 2)
        poly = torch.tensor(annotation['box_examples_coordinates'], dtype=torch.float32).reshape(-1, 4, 2)
        base = {'points': pts, 'boxes': torch.cat([pts - args.point_box_size_px / 2, pts + args.point_box_size_px / 2], 1),
                'labels': torch.zeros(len(pts), dtype=torch.long),
                'exemplars': torch.cat([poly.amin(1), poly.amax(1)], 1)[:3]}
        for seed in range(8):
            random.seed(seed)
            torch.manual_seed(seed)
            adapted_image, adapted = ds.transforms(original.copy(), dict(base, point_supervision=True))
            random.seed(seed)
            torch.manual_seed(seed)
            countgd_image, countgd = ds.transforms(original.copy(), base)
            assert torch.equal(adapted_image, countgd_image)
            assert torch.equal(adapted['exemplars'], countgd['exemplars'])
            assert torch.allclose(adapted['boxes'][:, :2], adapted['points'], atol=1e-6)
            assert (adapted['points'] >= 0).all() and (adapted['points'] <= 1).all()
            random.seed(seed)
            torch.manual_seed(seed)
            _, sample = ds[0]
            assert len(sample['boxes']) == int(sample['count']) == len(adapted['points'])
            assert int(sample['orig_count']) == len(pts)
            print(f'crop smoke seed={seed}: count {int(sample["orig_count"])}->{int(sample["count"])}, exemplars={len(sample["exemplars"])}')
        print('Crop smoke passed: original augmentation parity, border-center filtering, empty targets/exemplars, normalized centers/counts.')
