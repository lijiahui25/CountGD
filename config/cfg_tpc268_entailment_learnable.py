_base_ = ['cfg_tpc268_entailment.py']
# R08 control: one shared Lorentz curvature, initialized at c=1 (curvature=-c).
learn_curvature = True
curvature_init = 1.0
epochs = 20
