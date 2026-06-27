from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from .engine import decide_display_tier
from .models import AdmissionRecord, Recommendation, StudentProfile


SOURCE_INVENTORY_FILE = (
    Path(__file__).resolve().parent.parent / ".runtime" / "resource_update" / "source_inventory_audit.json"
)


def build_recommendation_diagnostics(
    profile: StudentProfile,
    records: Iterable[AdmissionRecord],
    recommendations: Iterable[Recommendation],
) -> dict[str, object]:
    record_list = list(records)
    recommendation_list = list(recommendations)
    filter_stats = _filter_stats(profile, record_list)
    eligible_records = filter_stats["eligible_records"]
    tier_counts = Counter()
    low_confidence_candidates = 0
    external_reference_candidates = 0
    missing_rank_candidates = 0

    for record in eligible_records:
        tier = decide_display_tier(profile, record)
        if tier:
            tier_counts[tier] += 1
        if _is_low_confidence(record.source):
            low_confidence_candidates += 1
        if _is_external_reference(record.source):
            external_reference_candidates += 1
        if not record.min_rank:
            missing_rank_candidates += 1

    result_tiers = Counter(item.tier for item in recommendation_list)
    low_confidence_results = sum(1 for item in recommendation_list if "低置信" in item.risk or "confidence=low" in item.reason)
    external_reference_results = sum(1 for item in recommendation_list if "外省生源数据" in item.risk or "生源省份参考" in item.reason)
    missing_rank_results = sum(1 for item in recommendation_list if not item.min_rank)
    inventory = _source_inventory_for(profile.province)

    return {
        "input": {
            "province": profile.province,
            "subject_type": profile.subject_type,
            "score": profile.score,
            "rank": profile.rank,
            "rank_source": profile.rank_source,
            "preferred_regions": profile.preferred_regions,
            "preferred_majors": profile.preferred_majors,
            "excluded_majors": profile.excluded_majors,
        },
        "candidate_pool": {
            "raw_records": len(record_list),
            "after_filters": len(eligible_records),
            "removed_by_province": filter_stats["removed_by_province"],
            "removed_by_city": filter_stats["removed_by_city"],
            "removed_by_excluded_major": filter_stats["removed_by_excluded_major"],
            "tier_candidates": dict(tier_counts),
            "missing_rank_candidates": missing_rank_candidates,
            "low_confidence_candidates": low_confidence_candidates,
            "external_reference_candidates": external_reference_candidates,
        },
        "results": {
            "total": len(recommendation_list),
            "tier_counts": dict(result_tiers),
            "missing_rank_results": missing_rank_results,
            "low_confidence_results": low_confidence_results,
            "external_reference_results": external_reference_results,
        },
        "source_inventory": inventory,
        "messages": _diagnostic_messages(profile, filter_stats, recommendation_list, inventory),
    }


def render_diagnostics(diagnostics: dict[str, object]) -> str:
    pool = diagnostics["candidate_pool"]
    results = diagnostics["results"]
    inventory = diagnostics.get("source_inventory") or {}
    messages = diagnostics.get("messages") or []
    lines = [
        "候选池诊断：",
        (
            f"- 原始候选 {pool['raw_records']} 条；过滤后 {pool['after_filters']} 条；"
            f"最终展示 {results['total']} 条。"
        ),
        (
            f"- 筛掉：省份不匹配 {pool['removed_by_province']} 条，"
            f"城市不匹配 {pool['removed_by_city']} 条，"
            f"排斥专业命中 {pool['removed_by_excluded_major']} 条。"
        ),
        f"- 候选分档：{_format_counts(pool['tier_candidates'])}。",
        (
            f"- 风险候选：缺可靠位次 {pool['missing_rank_candidates']} 条，"
            f"低置信参考 {pool['low_confidence_candidates']} 条，"
            f"外省参考 {pool['external_reference_candidates']} 条。"
        ),
    ]
    if inventory:
        lines.append(
            f"- 数据状态：{inventory.get('source_status', '未知')}；下一步：{inventory.get('next_action', '待继续核查')}。"
        )
    if messages:
        lines.append("诊断提示：")
        for message in messages:
            lines.append(f"- {message}")
    return "\n".join(lines)


def _filter_stats(profile: StudentProfile, records: list[AdmissionRecord]) -> dict[str, object]:
    preferred_regions = [
        item for item in profile.preferred_regions if item not in {"不限", "不限城市", "全国", "都可以"}
    ]
    eligible_records: list[AdmissionRecord] = []
    removed_by_province = 0
    removed_by_city = 0
    removed_by_excluded_major = 0

    for record in records:
        if record.province and profile.province and profile.province not in record.province:
            removed_by_province += 1
            continue
        if preferred_regions and record.city not in preferred_regions:
            removed_by_city += 1
            continue
        if profile.excluded_majors and any(keyword in record.major_name for keyword in profile.excluded_majors):
            removed_by_excluded_major += 1
            continue
        eligible_records.append(record)

    return {
        "eligible_records": eligible_records,
        "removed_by_province": removed_by_province,
        "removed_by_city": removed_by_city,
        "removed_by_excluded_major": removed_by_excluded_major,
    }


def _source_inventory_for(province: str) -> dict[str, object]:
    if not SOURCE_INVENTORY_FILE.exists():
        return {}
    try:
        rows = json.loads(SOURCE_INVENTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get("province") == province:
            keys = (
                "province",
                "source_status",
                "priority",
                "main_records_2025",
                "main_rank_2025",
                "main_rank_rate_2025",
                "medium_candidate_rank_2025",
                "low_candidate_rank_2025",
                "third_party_professional_rows_2025",
                "official_relevant_files",
                "next_action",
            )
            return {key: row.get(key) for key in keys}
    return {}


def _diagnostic_messages(
    profile: StudentProfile,
    filter_stats: dict[str, object],
    recommendations: list[Recommendation],
    inventory: dict[str, object],
) -> list[str]:
    messages: list[str] = []
    if profile.rank is None and profile.score is not None:
        messages.append("当前未拿到可靠位次，只能按分数窗口初筛；正式填报建议录入真实位次。")
    if filter_stats["removed_by_city"]:
        messages.append("城市偏好筛掉了一批候选；如果结果太少，优先放宽城市。")
    if profile.preferred_majors and not recommendations:
        messages.append("当前专业关键词没有形成可展示结果；系统没有自动改推计算机或其他热门专业。")
    if inventory.get("source_status") == "有低置信候选待人工确认":
        messages.append("本省存在低置信院校层数据，只能补视野，不能当精准专业组依据。")
    if inventory.get("source_status") in {"来源不足", "仅旧年库可参考"}:
        messages.append("本省缺少可直接用于 2025 冲稳保的院校最低分位，必须继续找官方投档/录取表。")
    if any("低置信" in item.risk for item in recommendations):
        messages.append("本次结果含低置信参考项，页面已放在参考档，正式方案需逐条核验。")
    if any(not item.min_rank for item in recommendations):
        messages.append("本次结果含位次未可靠入库项，排序和分档要谨慎看待。")
    return messages


def _format_counts(counts: object) -> str:
    if not isinstance(counts, dict) or not counts:
        return "无可分档候选"
    return "，".join(f"{tier}{count}条" for tier, count in counts.items())


def _is_low_confidence(source: str) -> bool:
    return "confidence=low" in source or "低置信院校层参考" in source


def _is_external_reference(source: str) -> bool:
    return "生源省份参考" in source or ("非" in source and "参考" in source)
