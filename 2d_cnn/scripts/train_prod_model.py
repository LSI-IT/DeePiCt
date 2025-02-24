import os
import argparse
import yaml

import numpy as np
import pandas as pd
import h5py

from tensorflow import test as tft
from tf_keras.callbacks import TensorBoard
from tf_keras.layers import Input
from tf_keras.callbacks import EarlyStopping
from tf_keras.optimizers import Adam

import datetime

from ConfigUtil import assemble_config
from UNet import *



def main():
    # Configuration
    srcdir = os.path.dirname(os.path.realpath(__file__))
    parser = get_cli()
    args = parser.parse_args()

    config = assemble_config(
        f"{srcdir}/defaults.yaml",
        args.config,
        subconfig_paths = [("training", "general"), ("training", "production")],
        cli_args = args
    )

    dataset_paths = args.datasets

    # Check GPU
    if tft.is_gpu_available():
        print("GPU is available! :)")
    else:
        print("GPU is not available! >:(")

    print(f"{f' DATA PREPARATION ':#^50}")
    datasets = []

    for p in dataset_paths: 
        print(f"Reading {p}...")
        with h5py.File(p, 'r') as f:
            features = f['features'][:]
            labels = f['labels'][:]
            sample_id = f.attrs["sample_id"]

            features = np.expand_dims(features, -1)
            labels = np.expand_dims(labels, -1)
            
            if config["normalize"]:
                print("Normalizing...")
                mean = features.mean()
                std = features.std()
                print(f"Before normalization: {mean: .2} +/-{std:.2}", end="\t")

                features -= mean
                features /= std
                print(f"After normalization: {features.mean(): .2} +/-{features.std():.2}")

            datasets.append([sample_id, features, labels])

    ids, features, labels = zip(*datasets)
    ids = np.array(ids)
    del datasets

    comb_idx = np.hstack([np.full(d.shape[0], i) for i, d in enumerate(features)])
    comb_features = np.vstack(features)
    comb_labels = np.vstack(labels)

    del features, labels # Free up memory

    print(f"{f' MODEL TRAINING ':#^50}")

    train_features = comb_features
    train_labels = comb_labels
    
    # Filter out fraction of all-empty patches
    if config["drop_empty"]:
        drop_idx = np.array([np.any(slice) for slice in train_labels]) | (np.random.random(train_labels.shape[0]) > config["drop_empty"])
        train_features = train_features[drop_idx]
        train_labels = train_labels[drop_idx]

    # Create model
    input_img = Input((comb_features.shape[1], comb_features.shape[2], 1), name='img')
    model = get_unet(input_img, n_filters=config["n_filters"], target_shape=train_labels.shape)
    model.compile(
        optimizer=Adam(learning_rate=config["lr"]),
        loss=neg_dice_coefficient,
        metrics=[dice_coefficient, "binary_crossentropy"]
    )

    # Fitting the model 
    results = model.fit(
        train_features, 
        train_labels, 
        batch_size=config["batch_size"],
        epochs=config["epochs"],
        verbose=2
    )

    print(f"{f' SAVING MODEL ':#^50}")
    model.save(config["model_output"])

def get_cli():
    parser = argparse.ArgumentParser(
        description="Train a new UNet to be used to create segmentations for new data."
    )

    parser.add_argument( 
        "-c",
        "--config",
        required=True,
        help="Configuration YAML file."
    )

    parser.add_argument( 
        "-d",
        "--datasets",
        required=True,
        nargs="+",
        help="Datasets used for training in HDF5 format."
    )
    
    return parser


if __name__ == "__main__":
    main()