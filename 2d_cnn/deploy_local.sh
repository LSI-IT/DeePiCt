#!/bin/bash

srcdir=$(realpath ${BASH_SOURCE[0]} | xargs dirname)
config_file=$1

snakemake \
    --snakefile "${srcdir}/snakefile" \
    --config config="${config_file}" \
    --forceall \
    --printshellcmds \
    --cores 1 \
    --resources gpu=1
