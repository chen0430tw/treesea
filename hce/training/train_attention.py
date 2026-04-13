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


def get_trainable_params() -> List[float]:
    """从当前 AFFINITY_GROUPS 和 _collapse_td_semantics 提取可训练参数。"""
    params = []
    # AFFINITY_GROUPS weights (15 params)
    for group_name in sorted(AFFINITY_GROUPS.keys()):
        for rule in AFFINITY_GROUPS[group_name]:
            params.append(rule[2])  # weight
    # collapse weights (9 params): survival(4) + race_dampen(1) + race(3) + coord(3) + inst(3)
    # 用固定顺序编码
    params.extend([0.35, 0.20, 0.20, 0.25])  # survival_need
    params.extend([0.55])                      # race_dampen
    params.extend([0.45, 0.30, 0.25])          # race_need
    params.extend([0.65, 0.20, 0.15])          # coordination_need
    params.extend([0.45, 0.25, 0.30])          # institution_need
    return params


def apply_params(params: List[float]) -> None:
    """将参数写回 AFFINITY_GROUPS（原地修改）。"""
    idx = 0
    for group_name in sorted(AFFINITY_GROUPS.keys()):
        new_rules = []
        for rule in AFFINITY_GROUPS[group_name]:
            new_rules.append((rule[0], rule[1], max(0.01, params[idx]), rule[3]))
            idx += 1
        AFFINITY_GROUPS[group_name] = new_rules
    # collapse weights 不能原地改（写在函数里），先跳过
    # 只训练 AFFINITY 权重


def perturb(params: List[float], sigma: float, n_affinity: int) -> List[float]:
    """对参数施加高斯扰动。"""
    new_params = []
    for i, p in enumerate(params):
        if i < n_affinity:
            # AFFINITY weights: 扰动范围 ±sigma
            new_p = p + random.gauss(0, sigma * max(abs(p), 0.1))
            new_params.append(max(0.01, new_p))
        else:
            # collapse weights: 小扰动
            new_p = p + random.gauss(0, sigma * 0.3)
            new_params.append(max(0.01, min(1.0, new_p)))
    return new_params


def train(
    samples: List[dict],
    n_iterations: int = 500,
    population_size: int = 20,
    sigma_init: float = 0.3,
    sigma_decay: float = 0.995,
    temperature: float = 1.0,
) -> Tuple[List[float], dict]:
    """随机搜索优化。

    每轮生成 population_size 个扰动参数，评估，保留最优。
    """
    # 计算 AFFINITY 规则数
    n_affinity = sum(len(rules) for rules in AFFINITY_GROUPS.values())

    best_params = get_trainable_params()
    best_result = evaluate_dataset(samples, temperature)
    best_score = best_result["pairwise_accuracy"] + 2.0 * best_result["top1_accuracy"]

    print(f"  Initial: pairwise={best_result['pairwise_accuracy']:.1%} top1={best_result['top1_accuracy']:.1%} score={best_score:.4f}")

    sigma = sigma_init
    no_improve = 0

    for it in range(n_iterations):
        improved = False

        for _ in range(population_size):
            trial_params = perturb(best_params, sigma, n_affinity)
            apply_params(trial_params)

            result = evaluate_dataset(samples, temperature)
            score = result["pairwise_accuracy"] + 2.0 * result["top1_accuracy"]

            if score > best_score:
                best_score = score
                best_params = trial_params[:]
                best_result = result
                improved = True

        # 恢复最优
        apply_params(best_params)

        sigma *= sigma_decay
        if improved:
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= 10:
                sigma = min(sigma * 1.5, sigma_init)
                no_improve = 0

        if (it + 1) % 10 == 0 or improved:
            print(
                f"  iter={it+1:4d}  pairwise={best_result['pairwise_accuracy']:.1%}  "
                f"top1={best_result['top1_accuracy']:.1%}  score={best_score:.4f}  "
                f"sigma={sigma:.4f}  {'*' if improved else ''}"
            )

    return best_params, best_result


def export_weights(params: List[float], output_path: str | Path) -> None:
    """导出训练后的权重为 JSON。"""
    idx = 0
    groups = {}
    for group_name in sorted(AFFINITY_GROUPS.keys()):
        rules = []
        for rule in AFFINITY_GROUPS[group_name]:
            rules.append({
                "env": rule[0],
                "cand": rule[1],
                "weight": round(params[idx], 4),
                "mode": rule[3],
            })
            idx += 1
        groups[group_name] = rules

    output = {
        "affinity_groups": groups,
        "n_params": len(params),
    }
    Path(output_path).write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Exported weights to {output_path}")


def main():
    dataset_path = Path(__file__).parent / "attention_dataset.json"
    samples = load_dataset(dataset_path)

    print(f"Loaded {len(samples)} training samples")
    print()

    # 评估基线
    print("=" * 70)
    print("  Baseline evaluation")
    print("=" * 70)

    baseline = evaluate_dataset(samples, temperature=1.0)
    print(f"  Pairwise accuracy: {baseline['pairwise_accuracy']:.1%} ({baseline['total_correct']}/{baseline['total_pairs']})")
    print(f"  Top-1 accuracy:    {baseline['top1_accuracy']:.1%}")
    print()

    # 训练
    print("=" * 70)
    print("  Training (random search)")
    print("=" * 70)

    random.seed(42)
    t0 = time.time()
    best_params, best_result = train(
        samples,
        n_iterations=200,
        population_size=30,
        sigma_init=0.4,
        temperature=1.0,
    )
    elapsed = time.time() - t0

    print(f"\n  Training complete in {elapsed:.1f}s")
    print()

    # 最终评估
    print("=" * 70)
    print("  Final evaluation")
    print("=" * 70)
    print(f"  Pairwise accuracy: {best_result['pairwise_accuracy']:.1%} ({best_result['total_correct']}/{best_result['total_pairs']})")
    print(f"  Top-1 accuracy:    {best_result['top1_accuracy']:.1%}")
    print()

    print("  --- Per-sample results ---")
    for s in sorted(best_result["per_sample"], key=lambda x: x["accuracy"]):
        status = "OK" if s["top1"] else "MISS"
        print(
            f"  [{status:4s}] {s['id']:35s}  "
            f"pairs={s['correct']}/{s['total']}  "
            f"acc={s['accuracy']:.0%}  "
            f"predicted={s['predicted_top']:25s}  expected={s['expected_top']}"
        )

    failures = [s for s in best_result["per_sample"] if not s["top1"]]
    print(f"\n  Failures: {len(failures)}/{len(samples)}")

    # 导出权重
    output_path = Path(__file__).parent / "trained_weights.json"
    export_weights(best_params, output_path)

    # 对比
    print()
    print("=" * 70)
    print("  Improvement")
    print("=" * 70)
    print(f"  Pairwise: {baseline['pairwise_accuracy']:.1%} -> {best_result['pairwise_accuracy']:.1%}")
    print(f"  Top-1:    {baseline['top1_accuracy']:.1%} -> {best_result['top1_accuracy']:.1%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
