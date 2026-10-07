# main
use_coco_eval = False
modelname = 'groundingdino'
# 位置编码
hidden_dim = 256
position_embedding = 'sine'
pe_temperatureH = 20
pe_temperatureW = 20
# Swin Transformer 视觉编码器
return_interm_indices = [1, 2, 3]
use_checkpoint = True
backbone = "swin_B_384_22k"
# 特征融合 + Top-K + 解码器
nheads = 8
num_queries = 900
enc_layers = 6
dec_layers = 6
dim_feedforward = 2048
dropout = 0.0
transformer_activation = 'relu'
pre_norm = False
query_dim = 4
num_patterns = 0
num_feature_levels = 4
enc_n_points = 4
dec_n_points = 4
two_stage_type = 'standard'
embed_init_tgt = True
use_text_enhancer = True
use_fusion_layer = True
use_transformer_ckpt = True
use_text_cross_attention = True
text_dropout = 0.0
fusion_dropout = 0.0
fusion_droppath = 0.1
# CountGD
aux_loss = True
dec_pred_bbox_embed_share = True
two_stage_bbox_embed_share = False
two_stage_class_embed_share = False
dn_box_noise_scale = 1.0
dn_label_noise_ratio = 0.5
dn_label_coef = 1.0
text_encoder_type = "bert-base-uncased"
sub_sentence_present = True
max_text_len = 256
# 匈牙利匹配
matcher_type = 'HungarianMatcher'
set_cost_class = 5.0
set_cost_bbox = 1.0
set_cost_giou = 0.0
focal_alpha = 0.25
# weight_dict
cls_loss_coef = 5.0
bbox_loss_coef = 1.0
giou_loss_coef = 0.0
no_interm_box_loss = False
interm_loss_coef = 1.0
# SetCriterion
focal_gamma = 2.0
# PostProcess
num_select = 900
nms_iou_threshold = -1
label_list = ['alcohol bottle', 'baguette roll', 'ball', 'banana', 'bead', 'bee', 'birthday candle', 'biscuit', 'boat', 'bottle', 'bowl', 'box', 'bread roll', 'brick', 'buffalo', 'bun', 'calamari ring', 'can', 'candle', 'cap', 'car', 'cartridge', 'cassette', 'cement bag', 'cereal', 'chewing gum piece', 'chopstick', 'clam', 'coffee bean', 'coin', 'cotton ball', 'cow', 'crane', 'crayon', 'croissant', 'crow', 'cup', 'cupcake', 'cupcake holder', 'fish', 'gemstone', 'go game piece', 'goat', 'goldfish snack', 'goose', 'ice cream', 'ice cream cone', 'instant noodle', 'jade stone', 'jeans', 'kidney bean', 'kitchen towel', 'lighter', 'lipstick', 'm&m piece', 'macaron', 'match', 'meat skewer', 'mini blind', 'mosaic tile', 'naan bread', 'nail', 'nut', 'onion ring', 'orange', 'pearl', 'pen', 'pencil', 'penguin', 'pepper', 'person', 'pigeon', 'plate', 'polka dot tile', 'potato', 'rice bag', 'roof tile', 'screw', 'shoe', 'spoon', 'spring roll', 'stair', 'stapler pin', 'straw', 'supermarket shelf', 'swan', 'tomato', 'watermelon', 'window', 'zebra']
# main
freeze_keywords = ['backbone.0', 'bert']      # for whole model, e.g. ['backbone.0', 'bert'] for freeze visual encoder and text encoder
param_dict_type = 'ddetr_in_mmdet'
lr = 0.0001                                   # base learning rate
weight_decay = 0.0001
# 数据集
max_labels = 90                               # pos + neg
data_aug_scales = [480, 512, 544, 576, 608, 640, 672, 704, 736, 768, 800]
data_aug_max_size = 1333
data_aug_scales2_resize = [400, 500, 600]
data_aug_scales2_crop = [384, 600]
data_aug_scale_overlap = None
masks = False
# 训练
batch_size = 4
lr_drop = 10
frozen_weights = None
# evaluate
val_label_list = ['ant', 'bird', 'book', 'bottle cap', 'bullet', 'camel', 'chair', 'chicken wing', 'donut', 'donut holder', 'flamingo', 'flower', 'flower pot', 'grape', 'horse', 'kiwi', 'milk carton', 'oyster', 'oyster shell', 'package of fresh cut fruit', 'peach', 'pill', 'polka dot', 'prawn cracker', 'sausage', 'seagull', 'shallot', 'shirt', 'skateboard', 'toilet paper roll']
box_threshold = 0.23
text_threshold = 0
# main
epochs = 30
clip_max_norm = 0.1
onecyclelr = False
save_checkpoint_interval = 10



dn_bbox_coef = 1.0
dn_labelbook_size = 91
backbone_freeze_keywords = None               # only for gdino backbone
lr_backbone = 1e-05                           # specific learning rate
lr_backbone_names = ['backbone.0', 'bert']
lr_linear_proj_mult = 1e-05
lr_linear_proj_names = ['ref_point_head', 'sampling_offsets']
ddetr_lr_param = False
multi_step_lr = False
lr_drop_list = [10, 20]
# dilation = False  # SwinTransformer 参数
pdetr3_bbox_embed_diff_each_layer = False
pdetr3_refHW = -1
random_refpoints_xy = False
fix_refpoints_hw = -1
dabdetr_yolo_like_anchor_update = False
dabdetr_deformable_encoder = False
dabdetr_deformable_decoder = False
use_deformable_box_attn = False
box_attn_type = 'roi_align'
dec_layer_number = None
decoder_layer_noise = False
dln_xy_noise = 0.2
dln_hw_noise = 0.2
add_channel_attention = False
add_pos_value = False
two_stage_pat_embed = 0
two_stage_add_query_num = 0
two_stage_learn_wh = False
two_stage_default_hw = 0.05
two_stage_keep_all_tokens = False
batch_norm_type = 'FrozenBatchNorm2d'

enc_loss_coef = 1.0
mask_loss_coef = 1.0
dice_loss_coef = 1.0
decoder_sa_type = 'sa'
decoder_module_seq = ['sa', 'ca', 'ffn']
dec_pred_class_embed_share = True
match_unstable_error = True
use_detached_boxes_dec_out = False
dn_scalar = 100