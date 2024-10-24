#!/usr/bin/env bash

VERBOSE=false
SNAKEFILE="$DEEPICT_ROOT/3d_cnn/snakefile"
JOBSCRIPT="$DEEPICT_ROOT/3d_cnn/jobscript.sh"

unset CONFIG_FILE

function Display_Help() {
   # Display Help
   echo "Run DeePiCt 3d_cnn on the cluster."
   echo
   echo "Usage: $0 (options)"
   echo "Options:"
   echo "  -c     REQUIRED.  Path to the yaml config file to use."
   echo "  -s     Path to the snakefile to use.  Defaults to $SNAKEFILE"
   echo "  -j     Path to the jobscript to use.  Defaults to $JOBSCRIPT"
   echo "  -h     Print this Help and exit."
   echo "  -v     Print verbose information."
   echo
}

function log_info() {
    local message
    message="$1"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[${timestamp}] - ${message}"
}

function log_verbose() {
    local message
    message="$1"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    if [ "$VERBOSE" = true ]; then
        echo "[${timestamp}] - ${message}"
    fi
}

while getopts :c:s:j:hv OPT ; do
  case $OPT in
    c)
      CONFIG_FILE="$OPTARG"
      ;;
    s)
      SNAKEFILE="$OPTARG"
      ;;
    j)
      JOBSCRIPT="$OPTARG"
      ;;
    h)
      Display_Help
      exit 1
      ;;
    v)
      VERBOSE=true
      ;;
    \:)
      printf "Argument missing from -%s option\n" $OPTARG
      printf "Usage: %s: [-c config_file] -s snakefile -j jobscript -h -v \n" ${0##*/}
      exit 2
      ;;
    \?)
      printf "Unknown option: -%s\n" $OPTARG
      printf "Usage: %s: [-c config_file] -s snakefile -j jobscript -h -v \n" ${0##*/}
      exit 2
      ;;
  esac >&2
done
# Remove all options processed by getopts.
shift $(($OPTIND - 1))

if [ -z "$CONFIG_FILE" ]; then
  echo "Missing the -c parameter" >&2
  Display_Help
  exit 1
fi

log_verbose "PYTHONPATH is: $PYTHONPATH"

if ! [ -f $CONFIG_FILE ]; then
    echo "The config file specified does not exist.  Please check the path." >&2
    echo "The config file specified was: $CONFIG_FILE" >&2
    echo "Exiting..." >&2
    exit 1
fi

if ! [ -f $SNAKEFILE ]; then
    echo "The snakefile specified does not exist.  Please check the path." >&2
    echo "The snakefile specified was: $SNAKEFILE" >&2
    echo "Exiting..." >&2
    exit 1
fi

if ! [ -f $JOBSCRIPT ]; then
    echo "The jobscript specified does not exist.  Please check the path." >&2
    echo "The jobscript specified was: $JOBSCRIPT" >&2
    echo "Exiting..." >&2
    exit 1
fi

log_verbose "SBATCH script contents:
#!/usr/bin/env bash

#SBATCH --output=logs/%j-%x.log
#SBATCH --job-name=snakemake
#SBATCH --parsable
#SBATCH --mem=20G
#SBATCH --time=10:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=sb-96

module purge
module load deepict/1.0.0

snakemake \
--snakefile \"$SNAKEFILE\" \
--cluster \"sbatch\" \
--config config=\"$CONFIG_FILE\" gpu=$CUDA_VISIBLE_DEVICES \
--jobscript \"$JOBSCRIPT\" \
--jobs 20 \
--printshellcmds \
--latency-wait 120 \
--max-jobs-per-second 1 \
--max-status-checks-per-second 0.1

End SBATCH script contents.
"

sbatch <<EOF
#!/usr/bin/env bash

#SBATCH --output=logs/%j-%x.log
#SBATCH --job-name=snakemake
#SBATCH --parsable
#SBATCH --mem=20G
#SBATCH --time=10:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=sb-96

module purge
module load deepict/1.0.0

snakemake \
--snakefile "$SNAKEFILE" \
--cluster "sbatch" \
--config config="$CONFIG_FILE" gpu=$CUDA_VISIBLE_DEVICES \
--jobscript "$JOBSCRIPT" \
--jobs 20 \
--printshellcmds \
--latency-wait 120 \
--max-jobs-per-second 1 \
--max-status-checks-per-second 0.1

EOF

exit 0