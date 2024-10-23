import argparse
import sys
import logging

parser = argparse.ArgumentParser()
parser.add_argument("-pythonpath", "--pythonpath", type=str)
parser.add_argument("-tomo_name", "--tomo_name", type=str)
parser.add_argument("-config_file", "--config_file", type=str)
parser.add_argument("-fold", "--fold", type=str, default="None")
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="Print out verbose messages.")
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
if pythonpath not in sys.path:
    sys.path.append(pythonpath)
    logger.debug(f"Added {pythonpath} to sys.path")

import os
import ast

from os import listdir
import shutil

import pandas as pd
import numpy as np
# import seaborn as sns
from file_actions.readers.tomograms import load_tomogram
from file_actions.writers.csv import build_tom_motive_list
from file_actions.writers.tomogram import write_tomogram
from tomogram_utils.coordinates_toolbox.clustering import get_cluster_centroids, \
    get_cluster_centroids_in_contact, get_cluster_centroids_colocalization
from paths.pipeline_dirs import get_probability_map_path, get_post_processed_prediction_path
from constants.config import Config
from constants.config import get_model_name
from networks.utils import get_training_testing_lists

config_file = args.config_file
config = Config(user_config_file=config_file)
tomo_name = args.tomo_name
fold = ast.literal_eval(args.fold)
calculate_motl = config.calculate_motl

model_path, model_name = get_model_name(config, fold)

snakemake_pattern = config.output_dir + "/predictions/" + model_name + "/" + tomo_name + "/" + config.pred_class + \
                    "/.{fold}.post_processed_prediction.mrc".format(fold=str(fold))

if isinstance(fold, int):
    tomo_training_list, tomo_testing_list = get_training_testing_lists(config=config, fold=fold)
    if tomo_name in tomo_testing_list:
        run_job = True
    else:
        run_job = False
else:
    run_job = True

if run_job:
    logger.info(f"Processing tomo: {tomo_name}")
    tomo_output_dir, output_path = get_probability_map_path(config.output_dir, model_name, tomo_name,
                                                            config.pred_class)

    for file in listdir(tomo_output_dir):
        if "motl" in file:
            logger.info(f"A motive list already exists: {file}")
            shutil.move(os.path.join(tomo_output_dir, file), os.path.join(tomo_output_dir, "prev_" + file))

    assert os.path.isfile(output_path)
    prediction_dataset = load_tomogram(path_to_dataset=output_path)
    output_shape = prediction_dataset.shape
    prediction_dataset_thr = 1 * (prediction_dataset > config.threshold)
    # set to zero the edges of tomogram
    if isinstance(config.ignore_border_thickness, int):
        ix = config.ignore_border_thickness
        iy, iz = ix, ix
    else:
        ix, iy, iz = config.ignore_border_thickness

    if iz > 0:
        prediction_dataset_thr[:iz, :, :] = np.zeros_like(prediction_dataset_thr[:iz, :, :])
        prediction_dataset_thr[-iz:, :, :] = np.zeros_like(prediction_dataset_thr[-iz:, :, :])
    if iy > 0:
        prediction_dataset_thr[:, :iy, :] = np.zeros_like(prediction_dataset_thr[:, :iy, :])
        prediction_dataset_thr[:, -iy:, :] = np.zeros_like(prediction_dataset_thr[:, -iy:, :])
    if ix > 0:
        prediction_dataset_thr[:, :, :ix] = np.zeros_like(prediction_dataset_thr[:, :, :ix])
        prediction_dataset_thr[:, :, -ix:] = np.zeros_like(prediction_dataset_thr[:, :, -ix:])

    logger.info(f"Region mask: {config.region_mask}")
    df = pd.read_csv(config.dataset_table, dtype={"tomo_name": str})
    df.set_index("tomo_name", inplace=True)
    masking_file = df[config.region_mask][tomo_name]
    clusters_output_path = get_post_processed_prediction_path(output_dir=config.output_dir,
                                                              model_name=model_name,
                                                              tomo_name=tomo_name,
                                                              semantic_class=config.pred_class)
    os.makedirs(tomo_output_dir, exist_ok=True)
    contact_mode = config.contact_mode

    if np.max(prediction_dataset_thr) == 0:
        clusters_labeled_by_size = prediction_dataset_thr
        centroids_list = []
        cluster_size_list = []
    else:
        logger.info(f"masking_file: {masking_file}")
        if isinstance(masking_file, float):
            logger.info(f"No intersecting mask available of the type {config.region_mask} for tomo {tomo_name}.")
            prediction_dataset_thr = prediction_dataset_thr.astype(np.int8)
            clusters_labeled_by_size, centroids_list, cluster_size_list = \
                get_cluster_centroids(dataset=prediction_dataset_thr,
                                      min_cluster_size=config.min_cluster_size,
                                      max_cluster_size=config.max_cluster_size,
                                      connectivity=config.clustering_connectivity)
        else:
            mask_indicator = load_tomogram(path_to_dataset=masking_file)
            shx, shy, shz = [np.min([shl, shp]) for shl, shp in
                             zip(mask_indicator.shape, prediction_dataset_thr.shape)]
            mask_indicator = mask_indicator[:shx, :shy, :shz]
            prediction_dataset_thr = prediction_dataset_thr[:shx, :shy, :shz]
            if contact_mode == "intersection":
                prediction_dataset_thr = mask_indicator.astype(np.int8) * prediction_dataset_thr.astype(np.int8)
                if np.max(prediction_dataset_thr) > 0:
                    clusters_labeled_by_size, centroids_list, cluster_size_list = \
                        get_cluster_centroids(dataset=prediction_dataset_thr,
                                              min_cluster_size=config.min_cluster_size,
                                              max_cluster_size=config.max_cluster_size,
                                              connectivity=config.clustering_connectivity)
            elif contact_mode == "contact":
                if np.max(prediction_dataset_thr) > 0:
                    clusters_labeled_by_size, centroids_list, cluster_size_list = \
                        get_cluster_centroids_in_contact(dataset=prediction_dataset_thr,
                                                         min_cluster_size=config.min_cluster_size,
                                                         max_cluster_size=config.max_cluster_size,
                                                         contact_mask=mask_indicator,
                                                         connectivity=config.clustering_connectivity)

            else:
                assert contact_mode == "colocalization"
                if np.max(prediction_dataset_thr) > 0:
                    clusters_labeled_by_size, centroids_list, cluster_size_list = \
                        get_cluster_centroids_colocalization(dataset=prediction_dataset_thr,
                                                             min_cluster_size=config.min_cluster_size,
                                                             max_cluster_size=config.max_cluster_size,
                                                             contact_mask=mask_indicator,
                                                             tol_contact=config.contact_distance,
                                                             connectivity=config.clustering_connectivity)

    clusters_output_path = get_post_processed_prediction_path(output_dir=config.output_dir, model_name=model_name,
                                                              tomo_name=tomo_name, semantic_class=config.pred_class)
    logger.info(f"clusters_output_path: {clusters_output_path}")
    clusters_output = 1*(clusters_labeled_by_size > 0)
    write_tomogram(output_path=clusters_output_path, tomo_data=clusters_output)

    os.makedirs(tomo_output_dir, exist_ok=True)
    if calculate_motl:
        motl_name = "motl_" + str(len(centroids_list)) + ".csv"
        logger.info(f"motl_name: {motl_name}")
        motl_file_name = os.path.join(tomo_output_dir, motl_name)

        if len(centroids_list) > 0:
            motive_list_df = build_tom_motive_list(
                list_of_peak_coordinates=centroids_list,
                list_of_peak_scores=cluster_size_list, in_tom_format=False)
            motive_list_df.to_csv(motl_file_name, index=False, header=False)
            logger.info(f"Motive list saved in {motl_file_name}")
        else:
            logger.info("Saving empty list!")
            motive_list_df = pd.DataFrame({})
            motive_list_df.to_csv(motl_file_name, index=False, header=False)

# For snakemake:
with open(file=snakemake_pattern, mode="w") as f:
    logger.info(f"Creating snakemake pattern: {snakemake_pattern}")
