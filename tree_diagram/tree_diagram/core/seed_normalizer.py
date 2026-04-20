"""ProblemSeed 归一化层：让内核接受任意自定义字段。

问题背景：
  Tree Diagram 内核只读取固定的气象领域字段（aim_coupling, field_noise 等）。
  用户如果在 seed.subject 里加 "nan_guard_coverage" 这种自定义字段，会被静默忽略，
  导致不同 seed 跑出一模一样的结果。

解法：
  在 pipeline 入口做一次归一化。自定义字段通过两种方式映射到内核字段：
    1. 显式别名（seed.metadata["field_aliases"]）
    2. 关键词语义路由（fallback）

  映射后的字段会和同名已有字段做加权平均。归一化过程记录在
  metadata["normalization_trace"] 里，方便调试。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .problem_seed import ProblemSeed


Section = Literal["subject", "environment", "resources"]


# ────────────────────────────────────────────────────────────────────
# 内核认识的字段白名单（从 worldline_kernel.py / background_inference.py 抽出）
# ────────────────────────────────────────────────────────────────────
KERNEL_KNOWN_SUBJECT: set[str] = {
    "output_power", "control_precision", "load_tolerance", "aim_coupling",
    "stress_level", "phase_proximity", "marginal_decay", "instability_sensitivity",
}
KERNEL_KNOWN_ENV: set[str] = {
    "field_noise", "social_pressure", "regulatory_friction",
    "network_density", "phase_instability",
}
KERNEL_KNOWN_RES: set[str] = {
    "budget", "infrastructure", "data_coverage", "population_coupling",
}

_KNOWN_BY_SECTION: dict[Section, set[str]] = {
    "subject": KERNEL_KNOWN_SUBJECT,
    "environment": KERNEL_KNOWN_ENV,
    "resources": KERNEL_KNOWN_RES,
}


# ────────────────────────────────────────────────────────────────────
# 语义关键词路由表
# 关键词按出现频率/专指度排序，前面的优先匹配
# ────────────────────────────────────────────────────────────────────
SEMANTIC_ROUTES: list[tuple[str, Section, str]] = [
    # ── Subject（训练 run 自身特征）───────────────────────────
    ("guard",            "subject", "control_precision"),     # nan_guard_coverage
    ("sanity",           "subject", "control_precision"),     # loss_sanity_checks
    ("check",            "subject", "control_precision"),
    ("validation",       "subject", "control_precision"),
    ("strictness",       "subject", "control_precision"),
    ("control_precision", "subject", "control_precision"),    # 专指，不匹配 mixed_precision
    ("numeric_precision", "subject", "control_precision"),
    ("consistency",      "subject", "aim_coupling"),          # direction_consistency
    ("convergence",      "subject", "aim_coupling"),
    ("direction",        "subject", "aim_coupling"),
    ("gradient_stability", "subject", "aim_coupling"),        # 专指：梯度稳定 = 收敛指向性
    ("gradient_norm",    "subject", "aim_coupling"),
    ("amplification",    "subject", "instability_sensitivity"),
    ("sensitivity",      "subject", "instability_sensitivity"),
    ("silent_failure",   "subject", "instability_sensitivity"),
    ("stress",           "subject", "stress_level"),
    ("decay",            "subject", "marginal_decay"),
    ("tolerance",        "subject", "load_tolerance"),
    ("severity",         "subject", "stress_level"),          # infection_severity
    ("lifespan",         "subject", "marginal_decay"),        # zombie_lifespan_tolerance (inverse)
    ("plausibility",     "subject", "phase_proximity"),       # output_plausibility
    ("visibility",       "subject", "control_precision"),     # symptom_visibility
    ("evasion",          "subject", "instability_sensitivity"),  # detection_evasion
    ("survivability",    "subject", "load_tolerance"),
    ("exit_discipline",  "subject", "control_precision"),     # early_exit_discipline
    ("band",             "subject", "phase_proximity"),       # gradient_norm_band
    ("monotonic",        "subject", "aim_coupling"),          # loss_monotonic_*
    ("margin",           "subject", "load_tolerance"),
    ("anti_",            "subject", "aim_coupling"),          # anti_frozen_signal etc.

    # ── Environment（训练环境）────────────────────────────────
    ("overflow",         "environment", "field_noise"),
    ("mixed_precision",  "environment", "field_noise"),
    ("noise",            "environment", "field_noise"),
    ("clamp_density",    "environment", "regulatory_friction"),
    ("enforcement",      "environment", "regulatory_friction"),
    ("contract",         "environment", "regulatory_friction"),
    ("clipping",         "environment", "regulatory_friction"),
    ("scaling",          "environment", "regulatory_friction"),
    ("propagation_risk", "environment", "phase_instability"),
    ("instability",      "environment", "phase_instability"),
    ("checkpoint",       "environment", "social_pressure"),
    ("dashboard",        "environment", "social_pressure"),
    ("alert",            "environment", "social_pressure"),
    ("attention",        "environment", "social_pressure"),
    ("masking",          "environment", "field_noise"),       # normalization_masking
    ("monitoring_freq",  "environment", "social_pressure"),
    ("batch_size",       "environment", "network_density"),
    ("density",          "environment", "network_density"),
    ("lr_stability",     "environment", "phase_instability"),
    ("data_quality",     "environment", "regulatory_friction"),
    ("safety",           "environment", "regulatory_friction"),

    # ── Resources（可用算力/预算）──────────────────────────────
    ("detection_budget", "resources", "budget"),
    ("monitoring_budget", "resources", "budget"),
    ("compute_budget",   "resources", "budget"),
    ("search_budget",    "resources", "budget"),
    ("budget",           "resources", "budget"),
    ("coverage",         "resources", "data_coverage"),
    ("log",              "resources", "data_coverage"),       # log_coverage/log_retention
    ("trace_granularity", "resources", "data_coverage"),
    ("granularity",      "resources", "data_coverage"),
    ("observability",    "resources", "data_coverage"),
    ("retention",        "resources", "data_coverage"),
    ("infrastructure",   "resources", "infrastructure"),
    ("infra_stability",  "resources", "infrastructure"),       # 专指：基础设施稳定性
    ("system_stability", "resources", "infrastructure"),
    ("coupling",         "resources", "population_coupling"),
    ("human_in_loop",    "resources", "population_coupling"),
    ("frequency",        "resources", "data_coverage"),

    # ────────────────────────────────────────────────────────────────────
    # Common English synonyms — non-domain-specific natural vocabulary users
    # are likely to reach for when they don't know Tree Diagram's exact
    # canonical names. Keep specifics above so they win by priority.
    # ────────────────────────────────────────────────────────────────────
    # Subject ────────────────────────────────────────────────────────
    ("capability",       "subject", "output_power"),
    ("capacity",         "subject", "output_power"),
    ("throughput",       "subject", "output_power"),
    ("strength",         "subject", "output_power"),
    ("horsepower",       "subject", "output_power"),           # "my_model_horsepower"
    ("accuracy",         "subject", "control_precision"),
    ("fidelity",         "subject", "control_precision"),
    ("rigor",            "subject", "control_precision"),
    ("alignment",        "subject", "aim_coupling"),
    ("coherence",        "subject", "aim_coupling"),
    ("resilience",       "subject", "load_tolerance"),
    ("robustness",       "subject", "load_tolerance"),
    ("durability",       "subject", "load_tolerance"),
    ("endurance",        "subject", "load_tolerance"),
    ("burden",           "subject", "stress_level"),
    ("load",             "subject", "stress_level"),           # "cognitive_load", "task_load"
    ("strain",           "subject", "stress_level"),
    ("workload",         "subject", "stress_level"),
    ("progress",         "subject", "phase_proximity"),
    ("maturity",         "subject", "phase_proximity"),
    ("nearness",         "subject", "phase_proximity"),
    ("proximity",        "subject", "phase_proximity"),
    ("fatigue",          "subject", "marginal_decay"),
    ("exhaustion",       "subject", "marginal_decay"),
    ("erosion",          "subject", "marginal_decay"),
    ("degradation",      "subject", "marginal_decay"),
    ("aging",            "subject", "marginal_decay"),
    ("fragility",        "subject", "instability_sensitivity"),
    ("chaos",            "subject", "instability_sensitivity"),
    ("volatility",       "subject", "instability_sensitivity"),
    ("exposure",         "subject", "instability_sensitivity"),  # "chaos_exposure"

    # Environment ────────────────────────────────────────────────────
    ("turbulence",       "environment", "field_noise"),
    ("uncertainty",      "environment", "field_noise"),
    ("error_rate",       "environment", "field_noise"),
    ("signal_quality",   "environment", "field_noise"),
    ("scrutiny",         "environment", "social_pressure"),
    ("oversight",        "environment", "social_pressure"),
    ("observation_pressure", "environment", "social_pressure"),
    ("compliance",       "environment", "regulatory_friction"),
    ("regulation",       "environment", "regulatory_friction"),
    ("rules",            "environment", "regulatory_friction"),
    ("constraint",       "environment", "regulatory_friction"),
    ("policy",           "environment", "regulatory_friction"),
    ("connectivity",     "environment", "network_density"),
    ("bandwidth",        "environment", "network_density"),
    ("concentration",    "environment", "network_density"),
    ("transition_rate",  "environment", "phase_instability"),

    # Resources ──────────────────────────────────────────────────────
    ("funding",          "resources", "budget"),
    ("cash",             "resources", "budget"),
    ("cost_cap",         "resources", "budget"),
    ("hardware",         "resources", "infrastructure"),
    ("compute",          "resources", "infrastructure"),       # "compute_horsepower", "compute_pool"
    ("machinery",        "resources", "infrastructure"),
    ("platform",         "resources", "infrastructure"),
    ("telemetry",        "resources", "data_coverage"),
    ("observation",      "resources", "data_coverage"),
    ("sensor",           "resources", "data_coverage"),
    ("instrumentation",  "resources", "data_coverage"),
    ("engagement",       "resources", "population_coupling"),
    ("adoption",         "resources", "population_coupling"),
    ("penetration",      "resources", "population_coupling"),
    ("community",        "resources", "population_coupling"),
]


@dataclass
class NormalizationTrace:
    """归一化过程的审计记录。"""
    preserved: dict[str, list[str]] = field(default_factory=dict)   # section → 原字段名
    aliased: list[tuple[str, str, str, str]] = field(default_factory=list)      # (orig_section, orig_name, dst_section, dst_field)
    routed: list[tuple[str, str, str, str, str]] = field(default_factory=list)  # (orig_section, orig_name, dst_section, dst_field, matched_keyword)
    unmatched: list[tuple[str, str]] = field(default_factory=list)  # (section, name)
    merged_fields: list[str] = field(default_factory=list)          # 多个自定义字段合并到同一内核字段
    filled_neutral: list[tuple[str, str]] = field(default_factory=list)  # 中性填充的内核字段 (section, field)

    def to_dict(self) -> dict:
        return {
            "preserved": self.preserved,
            "aliased": self.aliased,
            "routed": self.routed,
            "unmatched": self.unmatched,
            "merged_fields": self.merged_fields,
            "filled_neutral": self.filled_neutral,
        }


def _route_by_semantic(
    name: str,
    source_section: Section | None = None,
) -> tuple[Section, str, str] | None:
    """关键词语义路由。返回 (目标 section, 目标字段, 匹配的关键词) 或 None。

    匹配规则：
    1. 按关键词长度降序（更特指的优先）
    2. 如果提供了 source_section，优先选择与之相同的 section 的匹配
       （字段原本属于哪个层就尽量留在哪个层）
    """
    lower = name.lower()
    # 按长度降序匹配，避免短关键词抢走（"precision" 不该吃掉 "mixed_precision"）
    sorted_routes = sorted(SEMANTIC_ROUTES, key=lambda r: -len(r[0]))

    # 收集所有匹配
    matches: list[tuple[Section, str, str]] = []
    for keyword, section, target in sorted_routes:
        if keyword in lower:
            matches.append((section, target, keyword))

    if not matches:
        return None

    # 优先同 section 匹配
    if source_section:
        for m in matches:
            if m[0] == source_section:
                return m

    # 否则取第一个（最长的关键词）
    return matches[0]


def normalize_seed(
    seed: ProblemSeed,
    field_aliases: dict[str, tuple[Section, str]] | None = None,
    merge_policy: Literal["mean", "max", "replace"] = "mean",
    fill_missing_with_neutral: bool = False,
    neutral_value: float = 0.5,
) -> tuple[ProblemSeed, NormalizationTrace]:
    """将 ProblemSeed 归一化到内核可识别的字段集。

    Parameters
    ----------
    seed : ProblemSeed
        原始 seed，可能含自定义字段
    field_aliases : dict, optional
        显式别名映射 {原字段名: (目标 section, 目标内核字段)}
        优先级高于语义路由
    merge_policy : str
        多个自定义字段映射到同一内核字段时的合并策略：
        - "mean": 算术平均（默认）
        - "max":  取最大值
        - "replace": 后来者覆盖

    Returns
    -------
    (normalized_seed, trace)
    """
    aliases = field_aliases or {}
    trace = NormalizationTrace()

    # 收集所有需要写入的值：{(section, kernel_field): [values]}
    buckets: dict[tuple[Section, str], list[float]] = {}

    for section in ("subject", "environment", "resources"):
        src = getattr(seed, section)
        known = _KNOWN_BY_SECTION[section]
        preserved = []

        for name, value in src.items():
            v = float(value)

            # 1. 已知字段直通
            if name in known:
                buckets.setdefault((section, name), []).append(v)
                preserved.append(name)
                continue

            # 2. 显式别名
            if name in aliases:
                dst_section, dst_field = aliases[name]
                buckets.setdefault((dst_section, dst_field), []).append(v)
                trace.aliased.append((section, name, dst_section, dst_field))
                continue

            # 3. 语义路由（带 source_section 提示）
            routed = _route_by_semantic(name, source_section=section)
            if routed is not None:
                dst_section, dst_field, keyword = routed
                buckets.setdefault((dst_section, dst_field), []).append(v)
                trace.routed.append((section, name, dst_section, dst_field, keyword))
                continue

            # 4. 无匹配
            trace.unmatched.append((section, name))

        trace.preserved[section] = preserved

    # 合并策略
    def _merge(values: list[float]) -> float:
        if merge_policy == "max":
            return max(values)
        if merge_policy == "replace":
            return values[-1]
        return sum(values) / len(values)  # mean

    new_subject, new_env, new_res = {}, {}, {}
    section_map: dict[Section, dict] = {
        "subject": new_subject, "environment": new_env, "resources": new_res,
    }

    for (section, field_name), values in buckets.items():
        section_map[section][field_name] = _merge(values)
        if len(values) > 1:
            trace.merged_fields.append(f"{section}.{field_name}")

    # 中性填充：补齐内核关注的字段，避免内核取不可预期的 hardcoded 默认
    if fill_missing_with_neutral:
        for section, known_set in _KNOWN_BY_SECTION.items():
            dst = section_map[section]
            for kfield in known_set:
                if kfield not in dst:
                    dst[kfield] = neutral_value
                    trace.filled_neutral.append((section, kfield))

    normalized = ProblemSeed(
        title=seed.title,
        target=seed.target,
        constraints=list(seed.constraints),
        resources=new_res,
        environment=new_env,
        subject=new_subject,
    )

    return normalized, trace
