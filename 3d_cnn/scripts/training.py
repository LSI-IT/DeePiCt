import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("-config_file", "--config_file", type=str)
parser.add_argument("-pythonpath", "--pythonpath", type=str)
parser.add_argument("-fold", "--fold", type=str, default="None")
parser.add_argument("-gpu", "--gpu", help="cuda visible devices", type=str)
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="Print out verbose messages.")
args = parser.parse_args()

# Log arguments
if args.verbose:
    print(f"Arguments received: {args}")

pythonpath = args.pythonpath
config_file = args.config_file

if pythonpath not in sys.path:
    sys.path.append(pythonpath)
    if args.verbose:
        print(f"Added {pythonpath} to sys.path")

import os
import ast

import numpy as np
import shutil
import torch
import torch.nn as nn
import torch.optim as optim

from monai.losses.dice import GeneralizedDiceLoss

from networks.io import get_device, to_device
from networks.utils import get_training_testing_lists, \
    generate_data_loaders_data_augmentation
from networks.loss import DiceCoefficientLoss
from networks.routines import train, validate

from networks.unet import UNet3D
from networks.utils import save_unet_model
from networks.visualizers import TensorBoard_multiclass

from constants.config import Config, record_model
from constants.config import get_model_name


def load_checkpoint(filename: str):
    if args.verbose:
        print(f"Entered the load_checkpoint function with filename: {filename}")
    device = get_device()
    checkpoint = torch.load(filename, map_location=device)
    model_descriptor = checkpoint['model_descriptor']
    net_conf = {'final_activation': nn.Sigmoid(),
                'depth': model_descriptor.depth,
                'initial_features': model_descriptor.initial_features,
                "out_channels": model_descriptor.output_classes,
                "BN": model_descriptor.batch_norm,
                "encoder_dropout": model_descriptor.encoder_dropout,
                "decoder_dropout": model_descriptor.decoder_dropout}
    net = UNet3D(**net_conf)
    net = to_device(net=net, gpu=gpu)
    start_epoch = checkpoint['epoch']
    net.load_state_dict(checkpoint['model_state_dict'])
    optimizer = optim.Adam(net.parameters())
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    validation_loss = checkpoint['loss']
    # losslogger = checkpoint['losslogger']
    if args.verbose:
        print(f"Leaving the load_checkpoint function and returning net: {net} optimizer: {optimizer} start_epoch: {start_epoch} validation_loss: {validation_loss}")
    return net, optimizer, start_epoch, validation_loss


config = Config(args.config_file)
gpu = args.gpu
device = get_device()
fold = ast.literal_eval(args.fold)

# Generate relevant dirs
model_path, model_name = get_model_name(config, fold)
last_model_path = model_path[:-4] + "_last.pth"
best_model_path = model_path[:-4] + "_best.pth"
print(f"model_path: {model_path}")
print(f"model_name: {model_name}")
print(f"last_model_path: {last_model_path}")
print(f"best_model_path: {best_model_path}")
if fold is None:
    snakemake_pattern = Path(".done_patterns", model_path + "_None.pth.done")
else:
    snakemake_pattern = Path(".done_patterns", model_path + "_" + str(fold) + ".pth.done")

if os.path.exists(model_path) and not config.force_retrain:
    print("model exists already!")
else:
    print("training data loading process starting")
    logging_dir = os.path.join(config.output_dir, "logging")
    model_dir = os.path.join(config.output_dir, "models")
    models_table = os.path.join(model_dir, "models.csv")
    print(models_table)
    log_path = os.path.join(logging_dir, model_name)
    os.makedirs(log_path, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    assert config.loss in {"GeneralizedDice", "Dice"}, "Not a valid loss function."
    if config.loss == "GeneralizedDice":
        loss = GeneralizedDiceLoss()
    else:
        loss = DiceCoefficientLoss()
    loss = loss.to(device)
    metric = loss

    tomo_training_list, tomo_testing_list = get_training_testing_lists(config=config, fold=fold)
    model_descriptor = record_model(config=config, training_tomos=tomo_training_list,
                                    testing_tomos=tomo_testing_list, fold=fold)

    if config.force_retrain and os.path.isfile(last_model_path):
        net, optimizer, old_epoch, validation_loss = load_checkpoint(filename=last_model_path)
        best_net, best_optimizer, best_epoch, best_validation_loss = load_checkpoint(filename=model_path)
    else:
        net_conf = {'final_activation': nn.Sigmoid(),
                    'depth': config.depth,
                    'initial_features': config.initial_features,
                    "out_channels": len(config.semantic_classes),
                    "BN": config.batch_norm,
                    "encoder_dropout": config.encoder_dropout,
                    "decoder_dropout": config.decoder_dropout}

        net = UNet3D(**net_conf)
        net = to_device(net=net, gpu=gpu)
        validation_loss = np.inf
        best_epoch = -1
        old_epoch = -1
        optimizer = optim.Adam(net.parameters())

    logger = TensorBoard_multiclass(log_dir=log_path, log_image_interval=1)
    lr_scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.1,
                                                        patience=10, verbose=True)
    train_loader, val_loader = generate_data_loaders_data_augmentation(config=config,
                                                                       tomo_training_list=tomo_training_list,
                                                                       fold=fold)
    for epoch in range(old_epoch + 1, config.epochs):
        current_epoch = epoch


        train(model=net, loader=train_loader, optimizer=optimizer, loss_function=loss,
              epoch=current_epoch, device=device, log_interval=1, tb_logger=logger,
              log_image=False, lr_scheduler=lr_scheduler)

        step = current_epoch * len(train_loader.dataset)

        current_validation_loss = validate(model=net, loader=val_loader, loss_function=loss,
                                           metric=metric, device=device, step=step, tb_logger=logger,
                                           log_image_interval=None)

        # save best epoch
        if current_validation_loss <= validation_loss:
            best_epoch = current_epoch
            print(f"Best epoch! --> {best_epoch} with validation loss: {current_validation_loss}")
            validation_loss = current_validation_loss
            save_unet_model(path_to_model=model_path, epoch=current_epoch,
                            net=net, optimizer=optimizer, loss=current_validation_loss,
                            model_descriptor=model_descriptor)
        print(f"Epoch = {current_epoch} was not the best.")
        print(f"The current best is epoch = {best_epoch}")
        save_unet_model(path_to_model=last_model_path, epoch=current_epoch,
                        net=net, optimizer=optimizer, loss=current_validation_loss,
                        model_descriptor=model_descriptor)
    print("We have finished the training!")
    print(f"Best validation loss: {validation_loss} of epoch {best_epoch}")
    shutil.copy(src=model_path, dst=best_model_path)
# For snakemake:
print(f"snakemake_pattern: {snakemake_pattern}")
os.makedirs(os.path.dirname(snakemake_pattern), exist_ok=True)
print(f"Created the directories: {os.path.dirname(snakemake_pattern)}")
with open(file=snakemake_pattern, mode="w") as f:
    print(f"Creating snakemake pattern: {snakemake_pattern}")
