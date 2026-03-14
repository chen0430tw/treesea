#!/bin/bash
#SBATCH --job-name=qcu_bench_gpu
#SBATCH --partition=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --output=/mnt/d/treesea/qcu/jobs/bench_gpu_%j.out
#SBATCH --error=/mnt/d/treesea/qcu/jobs/bench_gpu_%j.err

echo "=== Job $SLURM_JOB_ID started at $(date) ==="
echo "Node: $(hostname)"
echo ""

# 环境
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export CUDA_VISIBLE_DEVICES=0
export PYTHONPATH=/mnt/d/treesea
cd /mnt/d/treesea

# GPU info
/usr/local/bin/nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
echo ""

python3 _bench_gpu.py

echo ""
echo "=== Done at $(date) ==="
