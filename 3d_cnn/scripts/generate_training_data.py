import argparse
import sys
import logging

parser = argparse.ArgumentParser()
parser.add_argument("-tomo_name", "--tomo_name", type=str)
parser.add_argument("-config_file", "--config_file", type=str)
parser.add_argument("-fold", "--fold", type=str, default="None")
parser.add_argument("-pythonpath", "--pythonpath", type=str)
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, type=bool, help="Print out verbose messages.")
args = parser.parse_args()

# Configure logger
log_level = logging.INFO
if args.verbose:
    log_level = logging.DEBUG

logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Log arguments
logger.debug(f"Arguments received: {args}")

pythonpath = args.pythonpath
tomo_name = args.tomo_name
config_file = args.config_file

if pythonpath not in sys.path:
    sys.path.append(pythonpath)
    logger.debug(f"Added {pythonpath} to sys.path")

import os
import ast
import numpy as np
import pandas as pd

from constants.config import Config
from tomogram_utils.volume_actions.actions import \
    generate_strongly_labeled_partition
from paths.pipeline_dirs import training_partition_path

logger.info("Reading configuration file and dataset table.")
config = Config(config_file)
df = pd.read_csv(config.dataset_table, dtype={"tomo_name": str})
df.set_index('tomo_name', inplace=True)
fold = ast.literal_eval(args.fold)
path_to_raw = df[config.processing_tomo][tomo_name]
labels_dataset_list = list()
for semantic_class in config.semantic_classes:
    mask_name = semantic_class + '_mask'
    path_to_mask = df[mask_name][tomo_name]
    labels_dataset_list.append(path_to_mask)

box_shape = (config.box_size, config.box_size, config.box_size)
output_path_dir, output_path = training_partition_path(output_dir=config.work_dir,
                                                       tomo_name=tomo_name,
                                                       fold=fold)
logger.info(f"Output directory: {output_path_dir}, Output path: {output_path}")
# print(output_path_dir)
os.makedirs(name=output_path_dir, exist_ok=True)
if os.path.isfile(output_path):
    logger.info(f"Training partition already exists")
else:
    logger.info("Training partition to be generated...")
    label_fractions_list = generate_strongly_labeled_partition(
        path_to_raw=path_to_raw,
        labels_dataset_paths_list=labels_dataset_list,
        segmentation_names=config.semantic_classes,
        output_h5_file_path=output_path,
        subtomo_shape=box_shape,
        overlap=config.overlap,
        min_label_fraction=config.min_label_fraction,
        max_label_fraction=config.max_label_fraction)
    logger.debug(f"label_fractions_list is: {label_fractions_list}")

    selected_cubes = np.where(np.array(label_fractions_list) > config.min_label_fraction)[0].shape
    if len(selected_cubes) == 0:
        selected_cubes = 0
    else:
        selected_cubes = selected_cubes[0]
    logger.info(f"{selected_cubes} out of {len(label_fractions_list)} cubes in partition file.")

# For snakemake
snakemake_pattern = "training_data/{tomo_name}/.train_partition.{fold}.done".format(tomo_name=tomo_name, fold=str(fold))
snakemake_pattern = os.path.join(config.work_dir, snakemake_pattern)
with open(snakemake_pattern, "w") as f:
    logger.info("Creating snakemake pattern")
