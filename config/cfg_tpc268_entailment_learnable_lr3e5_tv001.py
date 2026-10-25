_base_ = ['cfg_tpc268_entailment_learnable_lr3e5.py']
# LC-T04: relative to LC-T01, reduce only positive TV entailment weight.
lambda_tv = 0.01
