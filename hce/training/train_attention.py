"""
注意力权重训练器。

用训练数据集优化 AFFINITY_RULES 的权重，使输出排名尽可能匹配 expected_ranking。

损失函数: pairwise ranking loss (对于每对 (i, j)，如果 expected rank i < j 但 score i < score j，计入损失)
优化方法: 无梯度优化 (CMA-ES 或随机搜索)，因为 softmax + constraint 不可微
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 确保 hce 可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tree_diagram"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "qcu"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "honkai_core"))

from hce.integration.candidate_attention import (
    AFFINITY_GROUPS,
    _collapse_td_semantics,
    extract_candidate_features,
    compute_attention_scores,
)


def load_dataset(path: str | Path) -> List[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["samples"]


def evaluate_ranking(
    scores: List[float],
    candidate_ids: List[str],
    expected_ranking: List[str],
) -> Tuple[float, int, int]:
    """计算排名损失。

    返回: (loss, correct_pairs, total_pairs)
    """
    id_to_score = dict(zip(candidate_ids, scores))
    loss = 0.0
    correct = 0
    total = 0

    for i in range(len(expected_ranking)):
        for j in range(i + 1, len(expected_ranking)):
            higher_id = expected_ranking[i]
            lower_id = expected_ranking[j]
            if higher_id not in id_to_score or lower_id not in id_to_score:
                continue
            total += 1
            s_high = id_to_score[higher_id]
            s_low = id_to_score[lower_id]
            if s_high >= s_low:
                correct += 1
            else:
                margin = s_low - s_high
                loss += margin ** 2

    return loss, correct, total


def evaluate_dataset(samples: List[dict], temperature: float = 1.0) -> dict:
    """在整个数据集上评估当前权重。"""
    total_loss = 0.0
    total_correct = 0
    total_pairs = 0
    per_sample = []

    for sample in samples:
        env = sample["environment"]
        subject = sample.get("subject", {})
        candidates = sample["candidates"]
        expected = sample["expected_ranking"]

        # 构建 td_features（只用 seed 参数）
        td_features: Dict[str, float] = {}
        for k, v in env.items():
            td_features[f"seed_{k}"] = float(v)
        for k, v in subject.items():
            td_features[f"seed_{k}"] = float(v)

        # 候选
        cand_payloads = [c for c in candidates]
        cand_ids = [c["id"] for c in candidates]

        scores = compute_attention_scores(td_features, cand_payloads, temperature)

        loss, correct, pairs = evaluate_ranking(scores, cand_ids, expected)
        total_loss += loss
        total_correct += correct
        total_pairs += pairs

        # 判断 top-1 是否正确
        best_idx = scores.index(max(scores))
        top1_correct = cand_ids[best_idx] == expected[0]

        per_sample.append({
            "id": sample["id"],
            "loss": loss,
            "correct": correct,
            "total": pairs,
            "accuracy": correct / max(pairs, 1),
            "top1": top1_correct,
            "predicted_top": cand_ids[best_idx],
            "expected_top": expected[0],
        })

    accuracy = total_correct / max(total_pairs, 1)
    top1_acc = sum(1 for s in per_sample if s["top1"]) / max(len(per_sample), 1)

    return {
        "total_loss": total_loss,
        "total_correct": total_correct,
        "total_pairs": total_pairs,
        "pairwise_accuracy": accuracy,
        "top1_accuracy": top1_acc,
        "per_sample": per_sample,
    }


def main():
    dataset_path = Path(__file__).parent / "attention_dataset.json"
    samples = load_dataset(dataset_path)

    print(f"Loaded {len(samples)} training samples")
    print()

    # 评估当前权重
    print("=" * 70)
    print("  Evaluating current attention weights")
    print("=" * 70)

    result = evaluate_dataset(samples, temperature=1.0)

    print(f"  Pairwise accuracy: {result['pairwise_accuracy']:.1%} ({result['total_correct']}/{result['total_pairs']})")
    print(f"  Top-1 accuracy:    {result['top1_accuracy']:.1%}")
    print(f"  Total loss:        {result['total_loss']:.6f}")
    print()

    # 按准确率排序显示每个样本
    print("  --- Per-sample results ---")
    for s in sorted(result["per_sample"], key=lambda x: x["accuracy"]):
        status = "OK" if s["top1"] else "MISS"
        print(
            f"  [{status:4s}] {s['id']:35s}  "
            f"pairs={s['correct']}/{s['total']}  "
            f"acc={s['accuracy']:.0%}  "
            f"predicted={s['predicted_top']:25s}  expected={s['expected_top']}"
        )

    # 找出失败的样本
    failures = [s for s in result["per_sample"] if not s["top1"]]
    print(f"\n  Failures: {len(failures)}/{len(samples)}")
    for f in failures:
        print(f"    {f['id']}: predicted={f['predicted_top']} expected={f['expected_top']}")

    print()
    print("=" * 70)
    print(f"  Summary: {result['pairwise_accuracy']:.1%} pairwise, {result['top1_accuracy']:.1%} top-1")
    print("=" * 70)


if __name__ == "__main__":
    main()
