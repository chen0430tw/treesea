#!/bin/bash
#SBATCH --job-name=td_wind_sweep
#SBATCH --account=ENT114035
#SBATCH --partition=dev
#SBATCH --time=00:50:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --output=/work/twsuday816/treesea/tree_diagram/calibration/sweep_%j.out
#SBATCH --error=/work/twsuday816/treesea/tree_diagram/calibration/sweep_%j.err

set -euo pipefail

module load miniconda3/24.11.1

cd /work/twsuday816/treesea/tree_diagram

echo "[$(date '+%F %T')] python=$(which python) numpy=$(python -c 'import numpy; print(numpy.__version__)') scipy=$(python -c 'import scipy; print(scipy.__version__)')"
echo "[$(date '+%F %T')] Running sweep on $(hostname)"

export PYTHONIOENCODING=utf-8
python calibration/sweep_wind_params.py

echo "[$(date '+%F %T')] Done. Results:"
ls -la calibration/sweep_wind_params_localized.json
