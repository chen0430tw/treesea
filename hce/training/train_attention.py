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
    CROSS_WEIGHTS,
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


def evaluate_top1_margin(
    scores: List[float],
    candidate_ids: List[str],
    expected_ranking: List[str],
) -> Tuple[float, float, bool]:
    """评估 top-1 的领先 margin。

    返回: (margin, margin_loss, top1_correct)
    """
    if not expected_ranking:
        return 0.0, 0.0, False

    id_to_score = dict(zip(candidate_ids, scores))
    top_id = expected_ranking[0]
    top_score = id_to_score.get(top_id, float("-inf"))
    runner_up = max((score for cid, score in id_to_score.items() if cid != top_id), default=top_score)
    margin = top_score - runner_up
    margin_loss = max(0.0, 0.05 - margin)
    return margin, margin_loss, margin >= 0.0


def evaluate_dataset(samples: List[dict], temperature: float = 1.0) -> dict:
    """在整个数据集上评估当前权重。"""
    total_loss = 0.0
    total_correct = 0
    total_pairs = 0
    total_margin = 0.0
    total_margin_loss = 0.0
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
        margin, margin_loss, top1_correct = evaluate_top1_margin(scores, cand_ids, expected)
        total_loss += loss
        total_correct += correct
        total_pairs += pairs
        total_margin += margin
        total_margin_loss += margin_loss

        best_idx = scores.index(max(scores))

        per_sample.append({
            "id": sample["id"],
            "loss": loss,
            "correct": correct,
            "total": pairs,
            "accuracy": correct / max(pairs, 1),
            "top1": top1_correct,
            "top1_margin": margin,
            "top1_margin_loss": margin_loss,
            "predicted_top": cand_ids[best_idx],
            "expected_top": expected[0],
        })

    accuracy = total_correct / max(total_pairs, 1)
    top1_acc = sum(1 for s in per_sample if s["top1"]) / max(len(per_sample), 1)
    avg_margin = total_margin / max(len(per_sample), 1)
    avg_margin_loss = total_margin_loss / max(len(per_sample), 1)

    return {
        "total_loss": total_loss,
        "total_margin_loss": total_margin_loss,
        "total_correct": total_correct,
        "total_pairs": total_pairs,
        "pairwise_accuracy": accuracy,
        "top1_accuracy": top1_acc,
        "avg_top1_margin": avg_margin,
        "avg_top1_margin_loss": avg_margin_loss,
        "per_sample": per_sample,
    }


def objective_score(result: dict) -> float:
    """训练目标：优先 top-1，其次 pairwise 和领先 margin。"""
    return (
        result["pairwise_accuracy"]
        + 2.5 * result["top1_accuracy"]
        + 0.5 * result["avg_top1_margin"]
        - 0.5 * result["avg_top1_margin_loss"]
    )


def get_trainable_params() -> List[float]:
    """从 AFFINITY_GROUPS + CROSS_WEIGHTS 提取可训练参数。

    顺序：按 group name 排序 → 每组内按规则顺序 → CROSS_WEIGHTS 按 key 排序。
    apply_params 必须用完全相同的遍历顺序。
    """
    params = []
    n_affinity = 0
    for group_name in sorted(AFFINITY_GROUPS.keys()):
        for rule in AFFINITY_GROUPS[group_name]:
            params.append(rule[2])
            n_affinity += 1
    n_cross = 0
    for key in sorted(CROSS_WEIGHTS.keys()):
        params.append(CROSS_WEIGHTS[key])
        n_cross += 1
    return params


def apply_params(params: List[float]) -> None:
    """将参数写回 AFFINITY_GROUPS + CROSS_WEIGHTS。

    遍历顺序与 get_trainable_params 严格一致。
    """
    idx = 0
    for group_name in sorted(AFFINITY_GROUPS.keys()):
        new_rules = []
        for rule in AFFINITY_GROUPS[group_name]:
            new_rules.append((rule[0], rule[1], max(0.01, params[idx]), rule[3]))
            idx += 1
        AFFINITY_GROUPS[group_name] = new_rules
    for key in sorted(CROSS_WEIGHTS.keys()):
        CROSS_WEIGHTS[key] = max(0.01, params[idx])
        idx += 1


def perturb(params: List[float], sigma: float) -> List[float]:
    """对参数施加高斯扰动。"""
    new_params = []
    for p in params:
        new_p = p + random.gauss(0, sigma * max(abs(p), 0.1))
        new_params.append(max(0.01, new_p))
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
    best_params = get_trainable_params()
    best_result = evaluate_dataset(samples, temperature)
    best_score = objective_score(best_result)

    print(
        f"  Initial: pairwise={best_result['pairwise_accuracy']:.1%} "
        f"top1={best_result['top1_accuracy']:.1%} "
        f"margin={best_result['avg_top1_margin']:.4f} "
        f"score={best_score:.4f}"
    )

    sigma = sigma_init
    no_improve = 0

    for it in range(n_iterations):
        improved = False

        for _ in range(population_size):
            trial_params = perturb(best_params, sigma)
            apply_params(trial_params)

            result = evaluate_dataset(samples, temperature)
            score = objective_score(result)

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
                f"top1={best_result['top1_accuracy']:.1%}  "
                f"margin={best_result['avg_top1_margin']:.4f}  "
                f"score={best_score:.4f}  "
                f"sigma={sigma:.4f}  {'*' if improved else ''}"
            )

    return best_params, best_result


def train_with_restarts(
    samples: List[dict],
    n_restarts: int = 5,
    n_iterations: int = 200,
    population_size: int = 30,
    sigma_init: float = 0.4,
    temperature: float = 1.0,
) -> Tuple[List[float], dict]:
    """多次随机重启，降低单个 seed 卡局部最优的概率。"""
    base_params = get_trainable_params()[:]
    global_best_params: List[float] | None = None
    global_best_result: dict | None = None
    global_best_score = float("-inf")

    for restart in range(n_restarts):
        seed = 42 + restart
        random.seed(seed)
        apply_params(base_params)
        print()
        print(f"  Restart {restart + 1}/{n_restarts}  seed={seed}")
        params, result = train(
            samples,
            n_iterations=n_iterations,
            population_size=population_size,
            sigma_init=sigma_init,
            temperature=temperature,
        )
        score = objective_score(result)
        if score > global_best_score:
            global_best_score = score
            global_best_params = params[:]
            global_best_result = result
            print(f"  New global best from restart {restart + 1}: score={score:.4f}")

    assert global_best_params is not None
    assert global_best_result is not None
    apply_params(global_best_params)
    return global_best_params, global_best_result


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

    # CROSS_WEIGHTS
    cross = {}
    for key in sorted(CROSS_WEIGHTS.keys()):
        cross[key] = round(params[idx], 4)
        idx += 1

    output = {
        "affinity_groups": groups,
        "cross_weights": cross,
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

    t0 = time.time()
    best_params, best_result = train_with_restarts(
        samples,
        n_restarts=5,
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
    print(f"  Avg top-1 margin:  {best_result['avg_top1_margin']:.4f}")
    print()

    print("  --- Per-sample results ---")
    for s in sorted(best_result["per_sample"], key=lambda x: x["accuracy"]):
        status = "OK" if s["top1"] else "MISS"
        print(
            f"  [{status:4s}] {s['id']:35s}  "
            f"pairs={s['correct']}/{s['total']}  "
            f"acc={s['accuracy']:.0%}  "
            f"margin={s['top1_margin']:.4f}  "
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
    print(f"  Margin:   {baseline['avg_top1_margin']:.4f} -> {best_result['avg_top1_margin']:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
