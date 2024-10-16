#!/bin/bash

export srcdir=$(realpath ${BASH_SOURCE[0]} | xargs dirname)
config_file=$1
echo CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES
export PYTHONPATH=${srcdir}/src:$PYTHONPATH
echo PYTHONPATH=$PYTHONPATH

snakemake \
    --snakefile "${srcdir}/snakefile" \
    --config config="${config_file}" gpu=$CUDA_VISIBLE_DEVICES \
    --printshellcmds \
    --cores 1 --resources gpu=1

