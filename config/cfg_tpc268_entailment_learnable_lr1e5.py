_base_ = ['cfg_tpc268_entailment_learnable_lr3e5.py']
# LC-T05: relative to LC-T01, reduce only the ordinary optimizer group's LR.
lr = 1e-5
