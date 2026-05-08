"""OfferEvaluator Tool — 10-dimension weighted matrix comparison, 0 LLM."""

from __future__ import annotations

from typing import Any

DEFAULT_WEIGHTS: dict[str, float] = {
    "north_star_alignment": 0.25,
    "cv_match": 0.15,
    "seniority_level": 0.15,
    "compensation": 0.10,
    "growth_trajectory": 0.10,
    "remote_quality": 0.05,
    "company_reputation": 0.05,
    "tech_stack_modernity": 0.05,
    "speed_to_offer": 0.05,
    "cultural_signals": 0.05,
}

DIMENSION_LABELS = {
    "north_star_alignment": "北极星对齐",
    "cv_match": "简历匹配度",
    "seniority_level": "职级匹配",
    "compensation": "薪酬待遇",
    "growth_trajectory": "成长空间",
    "remote_quality": "远程办公质量",
    "company_reputation": "公司声誉",
    "tech_stack_modernity": "技术栈现代性",
    "speed_to_offer": "拿offer速度",
    "cultural_signals": "文化信号",
}


async def run_offer_evaluator(state: dict[str, Any]) -> dict[str, Any]:
    """OfferEvaluator Tool — compare multiple offers with weighted matrix."""
    offer_list: list[dict[str, Any]] = state.get("offer_list") or list(state.get("offers") or [])

    if not offer_list or len(offer_list) < 2:
        return {
            "offer_evaluation": {},
            "offer_comparison": {},
            "status": "OfferEvaluator 需要至少2个offer进行对比。",
        }

    # Get weights (user-provided or default)
    weights: dict[str, float] = dict(state.get("offer_weights") or DEFAULT_WEIGHTS)

    scores: dict[str, dict[str, float]] = {}
    weighted_totals: dict[str, float] = {}

    for offer in offer_list:
        offer_id = str(offer.get("offer_id", f"offer_{len(scores)}"))
        offer_scores: dict[str, float] = {}
        total = 0.0
        for dim, weight in weights.items():
            score = float(offer.get(dim, 50))
            offer_scores[dim] = score
            total += score * weight
        scores[offer_id] = offer_scores
        weighted_totals[offer_id] = round(total, 2)

    # Rank by weighted total
    ranking = sorted(weighted_totals.keys(), key=lambda k: weighted_totals[k], reverse=True)

    # Recommendation
    if len(ranking) >= 2 and weighted_totals[ranking[0]] - weighted_totals[ranking[1]] < 3:
        recommendation = f"建议：{ranking[0]} 和 {ranking[1]} 差距很小(<3分)，建议结合主观偏好判断。"
    elif ranking:
        recommendation = f"建议优先选择 {ranking[0]}，综合得分最高。"

    comparison = {
        "dimensions": {dim: {"label": DIMENSION_LABELS.get(dim, dim), "weight": w} for dim, w in weights.items()},
        "scores": scores,
        "weighted_totals": weighted_totals,
        "ranking": ranking,
        "recommendation": recommendation,
    }

    return {
        "offer_evaluation": comparison,
        "offer_comparison": comparison,
        "status": f"OfferEvaluator 完成对比，排名: {' > '.join(ranking)}",
    }
