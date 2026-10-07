import os
import sys
import json
import time
import random
import argparse
import datetime
from pathlib import Path

import torch
import numpy as np
from torch.utils.data import DataLoader, DistributedSampler

import util.misc as utils
from util.logger import setup_logger
from util.utils import BestMetricHolder
from engine import evaluate, train_one_epoch
from util.slconfig import DictAction, SLConfig
from util.get_param_dicts import get_param_dict
from util.utils import clean_state_dict
from datasets import build_dataset, get_coco_api_from_dataset


def get_args_parser():
    parser = argparse.ArgumentParser('CountGD training and evaluation script', add_help=False)
    parser.add_argument('--config_file', '-c', type=str, required=True)
    parser.add_argument('--options', nargs='+', action=DictAction,
        help='override some settings in the used config, the key-value pair '
        'in x=y format will be merged into config file.'
    )

    # 数据集参数
    parser.add_argument("--datasets", type=str, required=True, help='path to datasets json')
    parser.add_argument('--remove_difficult', action='store_true')
    parser.add_argument('--fix_size', action='store_true')

    # 训练参数
    parser.add_argument('--output_dir', default='')
    parser.add_argument('--note', default='', help='add some notes to the experiment')
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--seed', default=42, type=int)
    parser.add_argument('--resume', default='')
    parser.add_argument('--pretrain_model_path', default='checkpoints/')
    parser.add_argument('--finetune_ignore', type=str, nargs='+')
    parser.add_argument('--start_epoch', default=0, type=int, metavar='N')
    parser.add_argument('--eval', action='store_true')
    parser.add_argument('--num_workers', default=8, type=int)
    # parser.add_argument('--test', action='store_true')
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--find_unused_params', action='store_true')
    parser.add_argument('--save_results', action='store_true')
    parser.add_argument('--save_log', action='store_true')

    # 分布式训练参数
    parser.add_argument('--world_size', default=1, type=int, help='number of distributed processes')
    parser.add_argument('--dist_url', default='env://', help='url used to set up distributed training')
    parser.add_argument('--rank', default=0, type=int, help='number of distributed processes')
    parser.add_argument("--local_rank", type=int, help='local rank for DistributedDataParallel')
    parser.add_argument('--amp', action='store_true', help="Train with mixed precision")
    return parser


def build_model_main(args):
    from models.registry import MODULE_BUILD_FUNCS
    assert args.modelname in MODULE_BUILD_FUNCS._module_dict

    build_func = MODULE_BUILD_FUNCS.get(args.modelname)
    # models/GroundingDINO/groundingdino.py:build_groundingdino
    model, criterion, postprocessors = build_func(args)
    return model, criterion, postprocessors


def main(args):
    # 创建输出目录
    args.output_dir = args.output_dir or f'runs/{args.note}-{time.strftime("%m%d%H%M")}'
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    # 分布式训练配置
    utils.setup_distributed(args)  # util/misc.py
    # 配置文件
    print(f"Loading config file from {args.config_file}")
    time.sleep(args.rank * 0.02)
    cfg = SLConfig.fromfile(args.config_file)
    if args.options:
        cfg.merge_from_dict(args.options)
    if args.rank == 0:
        save_cfg_path = os.path.join(args.output_dir, "config_cfg.py")
        cfg.dump(save_cfg_path)  # config 目录下的配置文件合并 options 后的配置
        save_json_path = os.path.join(args.output_dir, "config_args_raw.json")
        with open(save_json_path, 'w') as f:
            json.dump(vars(args), f, indent=2)  # 原始 args 配置文件
    cfg_dict = cfg._cfg_dict.to_dict()
    args_vars = vars(args)
    for k, v in cfg_dict.items():
        if k not in args_vars:
            setattr(args, k, v)
        else:
            raise ValueError(f"Key {k} can used by args only")

    # 日志
    logger = setup_logger(output=os.path.join(args.output_dir, 'log.log'), distributed_rank=args.rank, name="countgd")
    # logger.info(f"world size: {args.world_size}")
    # logger.info(f"rank: {args.rank}")
    # logger.info(f"local_rank: {args.local_rank}")
    # logger.info(f"args: {args}")
    logger.info(f"Git: {utils.get_sha()}\n")
    logger.info("Command: " + ' '.join(sys.argv))
    if args.rank == 0:
        save_json_path = os.path.join(args.output_dir, "config_args_all.json")
        with open(save_json_path, 'w') as f:
            json.dump(vars(args), f, indent=2)  # args + cfg 配置
        logger.info(f"Full config saved to {save_json_path}")
    
    # 数据集配置
    with open(args.datasets) as f:
        dataset_meta = json.load(f)
    if args.use_coco_eval:
        args.coco_val_path = dataset_meta["val"][0]["anno"]

    device = torch.device(args.device)
    # 固定随机种子
    seed = args.seed + utils.get_rank()
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    logger.debug("build model...")
    model, criterion, postprocessors = build_model_main(args)
    model.to(device)
    logger.debug("build model, done.")

    model_without_ddp = model
    if args.distributed:
        model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.gpu], find_unused_parameters=args.find_unused_params)
        model._set_static_graph()
        model_without_ddp = model.module
    n_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f'number of params: {n_parameters}')
    
    # 冻结指定的参数
    if args.freeze_keywords is not None:
        for name, parameter in model.named_parameters():
            for keyword in args.freeze_keywords:
                if keyword in name:
                    parameter.requires_grad_(False)
                    break
    param_dicts = get_param_dict(args, model_without_ddp)  # util/get_param_dicts.py
    optimizer = torch.optim.AdamW(param_dicts, lr=args.lr, weight_decay=args.weight_decay)

    # 构建数据集
    logger.debug("build dataset...")
    dataset_val = build_dataset(image_set='val', args=args, datasetinfo=dataset_meta["val"][0])
    if not args.eval:
        dataset_train = build_dataset(image_set='train', args=args, datasetinfo=dataset_meta["train"][0])
        logger.debug(f'samples: {len(dataset_train)}')
        # num_of_dataset_train = len(dataset_meta["train"])
        # if num_of_dataset_train == 1:
        #     dataset_train = build_dataset(image_set='train', args=args, datasetinfo=dataset_meta["train"][0])
        # else:
        #     from torch.utils.data import ConcatDataset
        #     dataset_train_list = []
        #     for idx in range(len(dataset_meta["train"])):
        #         dataset_train_list.append(build_dataset(image_set='train', args=args, datasetinfo=dataset_meta["train"][idx]))
        #     dataset_train = ConcatDataset(dataset_train_list)
        # logger.debug(f'number of training dataset: {num_of_dataset_train}, samples: {len(dataset_train)}')

    logger.debug("build dataset, done.")

    if args.distributed:
        sampler_val = DistributedSampler(dataset_val, shuffle=False)
        if not args.eval:
            sampler_train = DistributedSampler(dataset_train)
    else:
        sampler_val = torch.utils.data.SequentialSampler(dataset_val)
        if not args.eval:
            sampler_train = torch.utils.data.RandomSampler(dataset_train)

    # 数据集加载器
    data_loader_val = DataLoader(dataset_val, 1, sampler=sampler_val, num_workers=args.num_workers, collate_fn=utils.collate_fn)
    if not args.eval:
        batch_sampler_train = torch.utils.data.BatchSampler(sampler_train, args.batch_size, True)
        data_loader_train = DataLoader(dataset_train, batch_sampler=batch_sampler_train, num_workers=args.num_workers, collate_fn=utils.collate_fn)

    # 学习率调度器
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, args.lr_drop)
    # if args.onecyclelr:
    #     lr_scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.lr, steps_per_epoch=len(data_loader_train), epochs=args.epochs, pct_start=0.2)
    # elif args.multi_step_lr:
    #     lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones=args.lr_drop_list)
    # else:
    #     lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, args.lr_drop)

    base_ds = get_coco_api_from_dataset(dataset_val)

    if args.frozen_weights:
        checkpoint = torch.load(args.frozen_weights, map_location='cpu')
        model_without_ddp.detr.load_state_dict(clean_state_dict(checkpoint['model']), strict=False)

    # 断点续训
    output_dir = Path(args.output_dir)
    if os.path.exists(os.path.join(args.output_dir, 'checkpoint.pth')):
        args.resume = os.path.join(args.output_dir, 'checkpoint.pth')
    
    if args.resume:
        checkpoint = torch.load(args.resume, map_location='cpu')
        # if args.resume.startswith('https'):
        #     checkpoint = torch.hub.load_state_dict_from_url(args.resume, map_location='cpu', check_hash=True)
        # else:
        #     checkpoint = torch.load(args.resume, map_location='cpu')
        model_without_ddp.load_state_dict(clean_state_dict(checkpoint['model']), strict=False)
        
        if not args.eval and 'optimizer' in checkpoint and 'lr_scheduler' in checkpoint and 'epoch' in checkpoint:
            optimizer.load_state_dict(checkpoint['optimizer'])
            lr_scheduler.load_state_dict(checkpoint['lr_scheduler'])
            args.start_epoch = checkpoint['epoch'] + 1

    if not args.resume and args.pretrain_model_path:
        from collections import OrderedDict

        checkpoint = torch.load(args.pretrain_model_path, map_location='cpu')['model']
        _ignorekeywordlist = args.finetune_ignore or []
        ignorelist = []

        def check_keep(keyname, ignorekeywordlist):
            for keyword in ignorekeywordlist:
                if keyword in keyname:
                    ignorelist.append(keyname)
                    return False
            return True

        logger.info(f"Ignore keys: {json.dumps(ignorelist, indent=2)}")
        _tmp_st = OrderedDict({k:v for k, v in utils.clean_state_dict(checkpoint).items() if check_keep(k, _ignorekeywordlist)})
        _load_output = model_without_ddp.load_state_dict(_tmp_st, strict=False)
        logger.info(str(_load_output))

    # 测试
    if args.eval:
        # engine.py:evaluate
        test_mae, test_stats = evaluate(model, criterion, postprocessors, 
            data_loader_val, base_ds, device, args.output_dir, args=args
        )
        # if args.output_dir:
        #     utils.save_on_master(coco_evaluator.coco_eval["bbox"].eval, output_dir / "eval.pth")

        log_stats = {**{f'test_{k}': v for k, v in test_stats.items()}}
        if args.output_dir and utils.is_main_process():
            with (output_dir / "log.txt").open("a") as f:
                f.write(json.dumps(log_stats) + "\n")
        return

    # 训练
    print("Start training...")
    start_time = time.time()
    best_map_holder = BestMetricHolder(init_res=100.0, better='small', use_ema=False)  # util/utils.py

    for epoch in range(args.start_epoch, args.epochs):
        epoch_start_time = time.time()
        if args.distributed:
            sampler_train.set_epoch(epoch)
        # engine.py:train_one_epoch
        train_stats = train_one_epoch(model, criterion, data_loader_train, optimizer, 
            device, epoch, args.clip_max_norm, lr_scheduler=lr_scheduler, args=args, 
            logger=(logger if args.save_log else None)
        )

        lr_scheduler.step()
        # if not args.onecyclelr:
        #     lr_scheduler.step()
        
        if args.output_dir:
            checkpoint_paths = [output_dir / 'checkpoint.pth']
            # 学习率下降或保存检查点间隔时保存检查点
            if (epoch + 1) % args.lr_drop == 0 or (epoch + 1) % args.save_checkpoint_interval == 0:
                checkpoint_paths.append(output_dir / f'checkpoint{epoch:04}.pth')
            # 同时保存 checkpoint.pth 和 checkpoint{epoch:04}.pth, 前者用于断点续训，后者用于固定时间间隔的存档
            for checkpoint_path in checkpoint_paths:
                weights = {
                    'model': model_without_ddp.state_dict(),
                    'optimizer': optimizer.state_dict(),
                    'lr_scheduler': lr_scheduler.state_dict(),
                    'epoch': epoch,
                    'args': args,
                }
                utils.save_on_master(weights, checkpoint_path)
        
        # 验证
        val_mae, test_stats = evaluate(
            model, criterion, postprocessors, data_loader_val, base_ds, device, args.output_dir,
            args=args, logger=(logger if args.save_log else None)
        )
        # 选择最优权重
        _isbest = best_map_holder.update(val_mae, epoch, is_ema=False)
        if _isbest:
            checkpoint_path = output_dir / 'checkpoint_best_regular.pth'
            utils.save_on_master({
                'model': model_without_ddp.state_dict(),
                'optimizer': optimizer.state_dict(),
                'lr_scheduler': lr_scheduler.state_dict(),
                'epoch': epoch,
                'args': args,
            }, checkpoint_path)
        log_stats = {
            **{f'train_{k}': v for k, v in train_stats.items()},
            **{f'test_{k}': v for k, v in test_stats.items()},
            'now_time': str(datetime.datetime.now())
        }
        
        epoch_time = time.time() - epoch_start_time
        epoch_time_str = str(datetime.timedelta(seconds=int(epoch_time)))
        log_stats['epoch_time'] = epoch_time_str

        if args.output_dir and utils.is_main_process():
            with (output_dir / "log.txt").open("a") as f:
                f.write(json.dumps(log_stats) + "\n")

            # for evaluation logs
            # if coco_evaluator:
            #     (output_dir / 'eval').mkdir(exist_ok=True)
            #     if "bbox" in coco_evaluator.coco_eval:
            #         filenames = ['latest.pth']
            #         if epoch % 50 == 0:
            #             filenames.append(f'{epoch:03}.pth')
            #         for name in filenames:
            #             torch.save(coco_evaluator.coco_eval["bbox"].eval, output_dir / "eval" / name)
    
    total_time = time.time() - start_time
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    print(f'Training time {total_time_str}')

    # 删除复制的文件
    # copyfilelist = vars(args).get('copyfilelist')
    # if copyfilelist and args.local_rank == 0:
    #     from datasets.data_util import remove

    #     for filename in copyfilelist:
    #         print(f"Removing: {filename}")
    #         remove(filename)


if __name__ == '__main__':
    args = get_args_parser().parse_args()
    main(args)
