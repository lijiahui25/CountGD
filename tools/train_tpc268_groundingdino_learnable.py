"""Fresh GroundingDINO initialization for the 20-epoch R08-GD-LC control."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.train_tpc268_groundingdino import (
    INITIALIZATION, INITIALIZATION_SHA256, load_groundingdino_state, sha256,
)


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
                not args.use_taxonomy_entailment or not args.learn_curvature or
                args.curvature_init != 1.0 or args.epochs != 20 or
                args.prompt_mode != 'full_taxonomy' or args.entailment_geometry != 'lorentz' or
                args.lambda_tt != .05 or args.lambda_tv != .05):
            raise ValueError('Expected the learnable-curvature, TT/TV-only, 20-epoch R08 protocol')
        import torch
        if not isinstance(model.taxonomy_aux.log_c, torch.nn.Parameter):
            raise ValueError('Curvature log_c must be a trainable parameter')
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
