#!/bin/bash
#SBATCH --job-name=qcu_cpu_bench
#SBATCH --partition=gtest
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=36
#SBATCH --time=00:20:00
#SBATCH --output=/work/twsuday816/qcu_cpu_bench_%j.out
#SBATCH --error=/work/twsuday816/qcu_cpu_bench_%j.err
#SBATCH --account=ENT114035

module load miniconda3/conda24.5.0_py3.9

export OMP_NUM_THREADS=1
export PYTHONPATH=/work/twsuday816/treesea

cd /work/twsuday816/treesea
echo "=== Node info ==="
hostname
lscpu | grep -E "Model name|CPU\(s\):|Core\(s\)"
echo "=== Start benchmark ==="
python3 qcu/jobs/bench_cpu_parallel.py
echo "=== Done ==="
