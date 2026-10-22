"""Fresh GroundingDINO initialization for the R08 initialization control.

The loading exception applies only to this entry point; normal CountGD training
and checkpoint evaluation retain their existing strict compatibility checks.
"""
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from util.checkpoint import is_auxiliary_key
from util.utils import clean_state_dict

INITIALIZATION = ROOT / 'checkpoints/groundingdino_swinb_cogcoor.pth'
INITIALIZATION_SHA256 = '46270f7a822e6906b655b729c90613e48929d0f2bb8b9b76fd10a856f3ac6ab7'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_groundingdino_state(model, state, logger, report_path):
    state = clean_state_dict(state)
    target = model.state_dict()
    # Exact CountGD-only parameter names, rather than permissive prefix loading.
    exemplar = {'feature_map_proj.weight', 'feature_map_proj.bias',
                'feature_map_encoder.norm.weight', 'feature_map_encoder.norm.bias'}
    for layer in range(3):
        for name in ('mlp.linear1', 'mlp.linear2', 'norm1', 'norm2',
                     'self_attn.out_proj'):
            exemplar.update(f'feature_map_encoder.layers.{layer}.{name}.{kind}'
                            for kind in ('weight', 'bias'))
        exemplar.update(f'feature_map_encoder.layers.{layer}.self_attn.in_proj_{kind}'
                        for kind in ('weight', 'bias'))
    auxiliary = {key for key in target if is_auxiliary_key(key)}
    missing, unexpected = set(target) - set(state), set(state) - set(target)
    if missing != exemplar | auxiliary or unexpected != {
            'label_enc.weight', 'bert.embeddings.position_ids'}:
        raise RuntimeError(f'Unexpected GroundingDINO mismatch: missing={sorted(missing)}, '
                           f'unexpected={sorted(unexpected)}')
    positions = state['bert.embeddings.position_ids']
    if positions.ndim != 2 or positions.shape[0] != 1 or not torch.equal(
            positions, torch.arange(positions.shape[-1]).unsqueeze(0)):
        raise RuntimeError('GroundingDINO BERT position_ids are not the fixed arange buffer')
    shape_mismatches = [key for key in set(state) & set(target)
                        if state[key].shape != target[key].shape]
    if shape_mismatches:
        raise RuntimeError(f'GroundingDINO shape mismatches: {shape_mismatches}')
    result = model.load_state_dict({key: value for key, value in state.items()
                                   if key not in unexpected}, strict=False)
    assert set(result.missing_keys) == missing and not result.unexpected_keys
    report = dict(initialization=str(INITIALIZATION), sha256=INITIALIZATION_SHA256,
                  loaded_tensor_keys=len(set(state) & set(target)),
                  countgd_random_initialized_keys=sorted(exemplar),
                  taxonomy_random_initialized_keys=sorted(auxiliary),
                  dropped_source_keys=sorted(unexpected),
                  optimizer_scheduler_rng_loaded=False)
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    logger.info('GroundingDINO initialization verified: %s', json.dumps(report))
    return result


def run():
    import main as training
    args = training.get_args_parser().parse_args()
    if args.resume or args.eval or args.start_epoch != 0:
        raise ValueError('This entry point only supports fresh training; evaluate using main.py')
    if Path(args.pretrain_model_path).resolve() != INITIALIZATION:
        raise ValueError('Expected the official GroundingDINO Swin-B checkpoint')
    if sha256(INITIALIZATION) != INITIALIZATION_SHA256:
        raise ValueError('GroundingDINO checkpoint SHA256 mismatch')
    if not args.output_dir or any((Path(args.output_dir) / name).exists()
                                  for name in ('checkpoint.pth', 'log.txt')):
        raise ValueError('Use a fresh explicit output directory')
    original = training.load_countgd_state
    initialized = False

    def initialize(model, state, logger, require_aux=False):
        nonlocal initialized
        if initialized or require_aux or args.resume:
            return original(model, state, logger, require_aux=require_aux)
        if (args.dataset_file != 'tpc268' or args.use_level_contrast or
                not args.use_taxonomy_entailment or args.learn_curvature or
                args.curvature_init != 1.0 or args.epochs != 30):
            raise ValueError('Expected the fixed-curvature, 30-epoch R08 protocol')
        result = load_groundingdino_state(
            model, state, logger, Path(args.output_dir) / 'initialization_report.json')
        initialized = True
        return result

    training.load_countgd_state = initialize
    try:
        training.main(args)
    finally:
        training.load_countgd_state = original


if __name__ == '__main__':
    run()
