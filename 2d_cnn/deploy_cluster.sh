#!/bin/bash

srcdir=$(realpath ${BASH_SOURCE[0]} | xargs dirname)
config_file=$1

srun -t 6:00:00 -c 1 --mem 4G \
    snakemake \
    --snakefile "${srcdir}/snakefile" \
    --cluster "sbatch" \
    --config config="${config_file}" \
    --jobscript "${srcdir}/jobscript.sh" \
    --jobs 20 \
    --printshellcmds \
    --latency-wait 30
