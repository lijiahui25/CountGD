_base_ = ['cfg_fsc147_test.py']
# Existing CountGD architecture, optimizer, freezing and center-only matching.
dataset_file = 'tpc268'
label_list = []
val_label_list = []
use_coco_eval = False
tpc268_root = 'data/TPC-268'
tpc268_annotation_file = 'data/tpc268_metadata/annotations/tpc268_annotations.json'
tpc268_taxonomy_ids_file = 'data/tpc268_metadata/annotations/tpc268_taxonomy_ids.json'
tpc268_taxonomy_vectors_file = 'data/tpc268_metadata/annotations/tpc268_taxonomy_vectors.json'
tpc268_train_split = 'data/tpc268_metadata/splits/tpc268_train.txt'
tpc268_val_split = 'data/tpc268_metadata/splits/tpc268_val.txt'
tpc268_test_split = 'data/tpc268_metadata/splits/tpc268_test.txt'
tpc268_split_json = 'data/tpc268_metadata/splits/tpc268_split.json'
tpc268_species_aliases_file = 'data/tpc268_metadata/species_aliases.json'
strict_taxonomy = False
prompt_mode = 'full_taxonomy'
num_exemplars = 3
point_box_size_px = 2.0
tpc268_augmentation = 'countgd_resize_crop'
use_level_contrast = False
use_taxonomy_entailment = False
entailment_geometry = 'lorentz'
aux_embed_dim = 128
aux_max_instances = 64
aux_text_chunk_size = 32
negatives_per_level = 16
temperature = 0.07
lambda_contrast = 0.1
lambda_tt = 0.05
lambda_tv = 0.05
bridge_weight = 1.0
curvature_init = 1.0
learn_curvature = False
cone_min_radius = 0.1
cone_radial_margin = 0.05
entailment_negatives_per_edge = 16
entailment_negative_margin = 0.1  # radians
entailment_negative_weight = 1.0
taxonomy_aux_protocol = 'negative_parents_valid_cones_v2'
aux_loss_warmup_epochs = 1
# All six methods share the original CountGD training resize/crop augmentation.
# Evaluation stays whole-image, without inference crop/SAM/correction.

# Keep all point labels; clip only intersecting exemplar boxes to image bounds.
tpc268_coordinate_policy = 'strict_points_clip_exemplars_v1'

# Shared by every baseline/auxiliary configuration; source files stay untouched.
tpc268_excluded_paths = [
    'Malus_domestica/fruit/Malus_domestica_fruit_1.jpg',
    'Musa_sapientum/fruit/Musa_sapientum_fruit_45.jpg',
    'Punica_granatum/fruit/Punica_granatum_fruit_17.jpg',
]
