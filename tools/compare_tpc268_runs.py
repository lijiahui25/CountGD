"""Compare real count outputs within matched caption/freezing/seed controls.

Example: python tools/compare_tpc268_runs.py runs/organ_baseline/val
         runs/organ_full/val --output runs/organ_comparison.json
No model inference, taxonomy accuracy or GT-driven prediction correction.
"""
import argparse
import json
import math
from pathlib import Path


INFERENCE_KEYS = ('split', 'threshold', 'text_threshold', 'counting_mode', 'crop',
                  'sam_tt_norm', 'exemplar_correction', 'num_exemplars',
                  'taxonomy_fingerprint', 'data_aug_scales', 'data_aug_max_size', 'fix_size')
TRAINING_KEYS = ('num_exemplars', 'num_queries', 'tpc268_augmentation', 'tpc268_coordinate_policy', 'tpc268_excluded_paths', 'data_aug_scales',
                 'data_aug_max_size', 'data_aug_scales2_resize', 'data_aug_scales2_crop',
                 'data_aug_scale_overlap', 'fix_size', 'point_box_size_px', 'batch_size',
                 'world_size', 'epochs', 'lr', 'lr_backbone', 'lr_drop', 'weight_decay',
                 'clip_max_norm', 'pretrain_model_path', 'text_encoder_type', 'taxonomy_fingerprint')


def read_run(directory, split):
    directory = Path(directory)
    metrics = json.loads((directory / f'{split}_metrics.json').read_text())
    counts = json.loads((directory / f'{split}_counts.json').read_text())
    training = metrics.get('training_protocol')
    required = ('prompt_mode', 'freeze_keywords', 'seed', 'use_level_contrast', 'use_taxonomy_entailment')
    if not isinstance(training, dict) or any(key not in training for key in required):
        raise ValueError(f'{directory}: missing actual training protocol; re-evaluate with current code')
    if metrics.get('prompt_mode') != training['prompt_mode']:
        raise ValueError(f'{directory}: inference caption differs from training caption')
    if any(key not in metrics for key in INFERENCE_KEYS) or any(key not in training for key in TRAINING_KEYS):
        raise ValueError(f'{directory}: incomplete comparison protocol')
    if metrics['split'] != split or not counts:
        raise ValueError(f'{directory}: wrong/empty counting split')
    rows = {}
    for row in counts:
        path = row['relative_path']
        if path in rows or row['split'] != split or row.get('prompt_mode') != metrics['prompt_mode']:
            raise ValueError(f'{directory}: duplicate image or inconsistent caption/split: {path}')
        if any(type(row[key]) is not int or row[key] < 0 for key in ('gt_count', 'pred_count')):
            raise ValueError(f'{directory}: invalid count: {path}')
        rows[path] = row
    errors = [row['pred_count'] - row['gt_count'] for row in rows.values()]
    n = len(errors)
    mae = math.fsum(abs(e) for e in errors) / n
    rmse = math.sqrt(math.fsum(e * e for e in errors) / n)
    if metrics.get('images') != n or any(not math.isclose(metrics[key], value, rel_tol=1e-6, abs_tol=1e-6)
                                       for key, value in (('mae', mae), ('rmse', rmse))):
        raise ValueError(f'{directory}: reported MAE/RMSE do not match per-image counts')
    return {'directory': str(directory), 'metrics': metrics, 'rows': rows, 'training': training}


def compare_runs(directories, split='val'):
    runs = [read_run(directory, split) for directory in directories]
    groups = {}
    for run in runs:
        training = run['training']
        # Different freezing settings need their own matching baseline.
        key = (training['prompt_mode'], tuple(sorted(training['freeze_keywords'] or [])), training['seed'])
        groups.setdefault(key, []).append(run)
    reports = []
    for (prompt, frozen, seed), group in groups.items():
        baselines = [run for run in group if not run['training']['use_level_contrast']
                     and not run['training']['use_taxonomy_entailment']]
        if len(baselines) != 1:
            raise ValueError(f'{prompt}, freeze={frozen}, seed={seed}: need exactly one matched baseline')
        baseline = baselines[0]
        results = []
        for run in group:
            for keys, current, reference in ((INFERENCE_KEYS, run['metrics'], baseline['metrics']),
                                             (TRAINING_KEYS, run['training'], baseline['training'])):
                for key in keys:
                    if current[key] != reference[key]:
                        raise ValueError(f'{run["directory"]}: unmatched baseline protocol: {key}')
            if run['rows'].keys() != baseline['rows'].keys():
                raise ValueError(f'{run["directory"]}: image set differs from baseline')
            improvements = []
            for path, row in run['rows'].items():
                base_row = baseline['rows'][path]
                for key in ('gt_count', 'species', 'organ', 'caption'):
                    if row[key] != base_row[key]:
                        raise ValueError(f'{run["directory"]}: different {key} for {path}')
                improvements.append(abs(base_row['pred_count'] - row['gt_count'])
                                    - abs(row['pred_count'] - row['gt_count']))
            results.append({
                'directory': run['directory'], 'mae': run['metrics']['mae'], 'rmse': run['metrics']['rmse'],
                'delta_mae': run['metrics']['mae'] - baseline['metrics']['mae'],
                'delta_rmse': run['metrics']['rmse'] - baseline['metrics']['rmse'],
                'images_improved': sum(value > 0 for value in improvements),
                'images_worsened': sum(value < 0 for value in improvements),
                'images_equal': sum(value == 0 for value in improvements),
                'auxiliary': {key: run['training'].get(key) for key in (
                    'use_level_contrast', 'use_taxonomy_entailment', 'entailment_geometry',
                    'taxonomy_aux_protocol', 'bridge_weight')},
            })
        reports.append({'prompt_mode': prompt, 'freeze_keywords': list(frozen), 'seed': seed,
                        'baseline': baseline['directory'], 'images': len(baseline['rows']), 'runs': results})
    return {'split': split, 'delta_convention': 'method minus matched baseline; negative is better',
            'groups': reports, 'interpretation': 'Count metrics only; conditioned queries are not pure visual embeddings'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='*', help='Directories containing split counts/metrics JSON')
    parser.add_argument('--split', choices=('val', 'test'), default='val')
    parser.add_argument('--output', help='Optional comparison JSON')
    parser.add_argument('--smoke-check', action='store_true', help='Explicit arithmetic/protocol checks; no dataset scores')
    args = parser.parse_args()
    if args.smoke_check:
        import tempfile
        # Hand-checkable outputs: baseline errors (-1,2), method errors (0,1).
        with tempfile.TemporaryDirectory() as scratch:
            roots = [Path(scratch) / name for name in ('baseline', 'full')]
            for root, predictions, active in zip(roots, ((1, 4), (2, 3)), (False, True)):
                root.mkdir()
                protocol = dict.fromkeys(TRAINING_KEYS)
                protocol.update(prompt_mode='organ', freeze_keywords=['bert'], seed=42,
                                use_level_contrast=active, use_taxonomy_entailment=active)
                metrics = dict.fromkeys(INFERENCE_KEYS)
                metrics.update(split='val', prompt_mode='organ', training_protocol=protocol, images=2,
                               mae=.5 if active else 1.5, rmse=math.sqrt(.5 if active else 2.5))
                rows = [{'relative_path': str(i), 'pred_count': prediction, 'gt_count': 2,
                         'species': 'sample', 'organ': 'fruit', 'caption': 'fruit .',
                         'split': 'val', 'prompt_mode': 'organ'} for i, prediction in enumerate(predictions)]
                (root / 'val_metrics.json').write_text(json.dumps(metrics))
                (root / 'val_counts.json').write_text(json.dumps(rows))
            report = compare_runs(roots)
            method = report['groups'][0]['runs'][1]
            assert method['delta_mae'] == -1 and method['images_improved'] == 2
            rows[0]['gt_count'] = 1
            (roots[1] / 'val_counts.json').write_text(json.dumps(rows))
            try:
                compare_runs(roots)
            except ValueError:
                pass
            else:
                raise AssertionError('Inconsistent per-image ground truth must be rejected')
        print('Comparison arithmetic and mismatched-data rejection passed; synthetic fixtures, not counting evaluation')
    else:
        if not args.directories:
            parser.error('Provide count-result directories or --smoke-check')
        report = compare_runs(args.directories, args.split)
        output = json.dumps(report, indent=2)
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(output)
        print(output)
