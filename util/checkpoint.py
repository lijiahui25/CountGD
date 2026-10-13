"""Explicit compatibility boundary between original CountGD and taxonomy heads."""
import re
from .utils import clean_state_dict


# Save the actual training setup alongside count results, including when a full
# checkpoint is evaluated through a baseline config that omits auxiliary heads.
TPC268_PROTOCOL_KEYS = (
    'prompt_mode', 'freeze_keywords', 'num_exemplars', 'num_queries',
    'tpc268_augmentation', 'data_aug_scales', 'data_aug_max_size',
    'data_aug_scales2_resize', 'data_aug_scales2_crop', 'data_aug_scale_overlap',
    'fix_size', 'point_box_size_px', 'batch_size', 'world_size', 'epochs',
    'lr', 'lr_backbone', 'lr_drop', 'weight_decay', 'clip_max_norm', 'seed',
    'pretrain_model_path', 'text_encoder_type', 'taxonomy_fingerprint',
    'use_level_contrast', 'use_taxonomy_entailment', 'entailment_geometry',
    'taxonomy_aux_protocol', 'lambda_contrast', 'lambda_tt', 'lambda_tv',
    'bridge_weight', 'aux_max_instances', 'aux_loss_warmup_epochs',
    'cone_min_radius', 'cone_radial_margin', 'entailment_negatives_per_edge',
    'entailment_negative_margin', 'entailment_negative_weight',
)


def tpc268_training_protocol(args):
    return {key: getattr(args, key, None) for key in TPC268_PROTOCOL_KEYS}


def is_auxiliary_key(key):
    return bool(re.fullmatch(r'taxonomy_aux\.(?:(?:query_proj|text_proj)\.(?:0|2)\.(?:weight|bias)|log_alpha_[vt]|log_c|temperature)', key))


def load_countgd_state(model, state, logger, require_aux=False):
    state = clean_state_dict(state)
    model_state = model.state_dict()
    missing = sorted(set(model_state) - set(state))
    unexpected = sorted(set(state) - set(model_state))
    logger.info(f'Checkpoint missing keys: {missing}; unexpected keys: {unexpected}')
    bad_missing = [k for k in missing if not is_auxiliary_key(k) or require_aux]
    bad_unexpected = [k for k in unexpected if not is_auxiliary_key(k)]
    if bad_missing or bad_unexpected:
        raise RuntimeError(f'CountGD checkpoint mismatch: missing={bad_missing}, unexpected={bad_unexpected}')
    # Size mismatches are still rejected by PyTorch; strict=False only admits known heads.
    return model.load_state_dict(state, strict=False)
