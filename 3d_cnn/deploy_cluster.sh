#!/bin/bash

export srcdir=$(realpath ${BASH_SOURCE[0]} | xargs dirname)
config_file=$1
export PYTHONPATH=${srcdir}/src:$PYTHONPATH
echo PYTHONPATH=$PYTHONPATH

module load deepict/1.0.0
module load cuda/12.2.2

srun -t 10:00:00 -c 1 --mem 4G \
snakemake \
--snakefile "${srcdir}/snakefile" \
--cluster "sbatch" \
--config config="${config_file}" gpu=$CUDA_VISIBLE_DEVICES \
--jobscript "${srcdir}/jobscript.sh" \
--jobs 20 \
--printshellcmds \
--latency-wait 120 \
--max-jobs-per-second 1 \
--max-status-checks-per-second 0.1
