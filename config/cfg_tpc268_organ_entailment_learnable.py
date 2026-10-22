_base_ = ['cfg_tpc268_organ_full.py']
# R06 control: organ caption, TT/TV only, one shared learnable curvature.
use_level_contrast = False
learn_curvature = True
curvature_init = 1.0
epochs = 20
