# result_merge.py
"""
结果合并器。

将 Tree Diagram、QCU、Honkai Core 三个系统的输出合并为统一的最终结果。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ResultMerger:
    """三系统结果合并器。"""

    def merge(
        self,
        request_id: str,
        tree_output: Optional[dict] = None,
        sea_output: Optional[dict] = None,
        hc_output: Optional[dict] = None,
    ) -> dict:
        """合并各系统输出为统一结果。

        Parameters
        ----------
        request_id : str
        tree_output, sea_output, hc_output : dict, optional

        Returns
        -------
        dict
            包含 final_selection, final_ranking, energy_summary, risk_summary
        """
        final_ranking = self._build_ranking(tree_output, sea_output, hc_output)
        final_selection = self._select_best(final_ranking)
        energy_summary = self._extract_energy(hc_output)
        risk_summary = self._extract_risk(hc_output)

        return {
            "request_id": request_id,
            "final_selection": final_selection,
            "final_ranking": final_ranking,
            "energy_summary": energy_summary,
            "risk_summary": risk_summary,
        }

    def _build_ranking(
        self,
        tree_output: Optional[dict],
        sea_output: Optional[dict],
        hc_output: Optional[dict],
    ) -> List[Dict[str, Any]]:
        """构建统一排名。"""
        candidates: Dict[str, Dict[str, Any]] = {}

        # 从 Tree 提取
        if tree_output:
            oracle = tree_output.get("oracle_details", {})
            for cs in oracle.get("candidate_set", []):
                cid = cs.get("candidate_id", "unknown")
                candidates[cid] = {
                    "candidate_id": cid,
                    "tree_score": cs.get("score", 0.0),
                    "collapse_score": None,
                    "risk_level": None,
                    "composite_score": cs.get("score", 0.0),
                }

            # 如果没有 candidate_set，用 best_worldline
            if not candidates:
                best = tree_output.get("best_worldline", {})
                if best:
                    candidates["td_best"] = {
                        "candidate_id": "td_best",
                        "tree_score": best.get("score", 0.0),
                        "collapse_score": None,
                        "risk_level": None,
                        "composite_score": best.get("score", 0.0),
                    }

        # 从 QCU 补充
        if sea_output:
            collapse_results = sea_output.get("collapse_results", [])
            entries = sea_output.get("entries", [])
            items = collapse_results or entries

            for cr in items:
                cid = cr.get("candidate_id", cr.get("run_id", "unknown"))
                if cid in candidates:
                    candidates[cid]["collapse_score"] = cr.get("collapse_score", cr.get("C_end", 0.0))
                else:
                    candidates[cid] = {
                        "candidate_id": cid,
                        "tree_score": None,
                        "collapse_score": cr.get("collapse_score", cr.get("C_end", 0.0)),
                        "risk_level": None,
                        "composite_score": cr.get("collapse_score", cr.get("C_end", 0.0)),
                    }

        # 从 HC 补充风险和 tree_score
        if hc_output:
            for re in hc_output.get("risk_entries", []):
                hc_cid = re.get("candidate_id", "unknown")
                # HC candidate_id 是短名，QCU 的是 run_id 长路径
                # 尝试精确匹配，再尝试尾部匹配
                matched = None
                if hc_cid in candidates:
                    matched = hc_cid
                else:
                    for full_cid in candidates:
                        if full_cid.endswith("/" + hc_cid):
                            matched = full_cid
                            break
                if matched:
                    candidates[matched]["risk_level"] = re.get("risk_level", "safe")
                    # 从 detail 补充 tree_score
                    detail = re.get("detail", {})
                    if detail.get("tree_score") is not None and candidates[matched].get("tree_score") is None:
                        candidates[matched]["tree_score"] = detail["tree_score"]

        # 计算 composite_score
        for c in candidates.values():
            tree_s = c.get("tree_score") or 0.0
            sea_s = c.get("collapse_score") or 0.0
            c["composite_score"] = 0.6 * tree_s + 0.4 * (1.0 - sea_s)

        # 过滤掉仅由 Tree Diagram fallback 产生且无 QCU 数据的占位候选
        real_candidates = [
            c for c in candidates.values()
            if c.get("collapse_score") is not None or c.get("tree_score", 0) > 0
        ]
        if not real_candidates:
            real_candidates = list(candidates.values())

        # 排序
        ranking = sorted(real_candidates, key=lambda x: x["composite_score"], reverse=True)
        return ranking

    def _select_best(self, ranking: List[Dict[str, Any]]) -> dict:
        """选出最佳候选。"""
        if not ranking:
            return {}
        best = ranking[0]
        return {
            "candidate_id": best["candidate_id"],
            "composite_score": best["composite_score"],
            "tree_score": best.get("tree_score"),
            "collapse_score": best.get("collapse_score"),
        }

    def _extract_energy(self, hc_output: Optional[dict]) -> dict:
        if not hc_output:
            return {}
        energy = hc_output.get("energy_estimate", {})
        return {
            "total_energy": energy.get("total_energy", 0.0),
            "state": energy.get("state", "unknown"),
            "gain_factor": energy.get("gain_factor", 0.0),
            "density": energy.get("density", 0.0),
        }

    def _extract_risk(self, hc_output: Optional[dict]) -> dict:
        if not hc_output:
            return {}
        risk_entries = hc_output.get("risk_entries", [])
        rec = hc_output.get("recommendation", {})
        return {
            "action": rec.get("action", "unknown"),
            "confidence": rec.get("confidence", 0.0),
            "writeback_allowed": rec.get("writeback_allowed", True),
            "n_entries": len(risk_entries),
            "n_critical": sum(
                1 for r in risk_entries
                if r.get("risk_level") in ("critical", "terminal")
            ),
        }
