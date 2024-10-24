#!/bin/bash
#SBATCH --output={job.params.logdir}/%j-%x.log
#SBATCH --job-name={job.rule}
#SBATCH --parsable

#SBATCH --mem={job.params.memory}
#SBATCH --time={job.params.walltime}
#SBATCH --ntasks={job.params.ntasks}
#SBATCH --cpus-per-task={job.params.cores}
#SBATCH --nodes={job.params.nodes}
{job.params.gres}

module purge
module load deepict/1.0.0

export DISPLAY=0.0
export PYTHONUNBUFFERED=1

echo CLUSTER NAME: $SLURM_CLUSTER_NAME
echo CLUSTER NODE: $SLURMD_NODENAME

{exec_job}
