_base_ = ['cfg_tpc268_entailment_learnable_lr3e5.py']
# LC-T06: relative to LC-T01, extend only the TT/TV weight warmup.
aux_loss_warmup_epochs = 3
