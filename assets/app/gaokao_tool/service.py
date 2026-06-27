from __future__ import annotations

import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from .data_loader import load_admission_records, load_score_rank_records
from .diagnostics import build_recommendation_diagnostics, render_diagnostics
from .engine import recommend
from .models import Recommendation, ScoreRankRecord, StudentProfile
from .real_admission import has_real_admission_db
from .web_research import render_research_plan


CITY_PROVINCE_REGISTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "city_province_registry.json"
PROVINCES = {
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
    "新疆", "香港", "澳门",
}


def parse_keywords(raw: str) -> List[str]:
    return [item.strip() for item in re.split(r"[,，、;/；\s]+", raw) if item.strip()]


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    return int(stripped)


@lru_cache(maxsize=1)
def _load_city_province_registry() -> dict[str, str]:
    if not CITY_PROVINCE_REGISTRY_FILE.exists():
        return {}
    try:
        raw = json.loads(CITY_PROVINCE_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(city).strip(): str(province).strip() for city, province in raw.items() if city and province}


def _normalize_subject_type(province: str, subject_type: str) -> tuple[str, str | None]:
    value = subject_type.strip()
    if not value:
        return value, None
    if value in {"物理类", "历史类", "综合", "普通类", "理科", "文科"}:
        return value, None
    if province in {"北京", "上海", "浙江", "山东", "天津", "海南"}:
        return "综合", f"已将选科“{value}”按新高考综合口径查询。"
    if "物" in value:
        return "物理类", f"已将选科“{value}”归一为物理类。"
    if "史" in value or "文" in value:
        return "历史类", f"已将选科“{value}”归一为历史类。"
    return value, None


def estimate_rank(province: str, subject_type: str, score: int) -> tuple[int | None, str]:
    records = [
        item
        for item in load_score_rank_records()
        if item.province == province and item.subject_type == subject_type
    ]
    if not records and province in {"北京", "上海", "浙江", "山东", "天津", "海南"}:
        records = [
            item
            for item in load_score_rank_records()
            if item.province == province and item.subject_type in {"综合", "普通类"}
        ]
    if not records:
        return None, "missing_score_rank_table"
    records = sorted(records, key=_rank_record_priority)

    exact = next((item for item in records if item.score == score), None)
    if exact:
        source_suffix = f":{exact.source_type}" if exact.source_type else ""
        return exact.rank, f"estimated_from_score:{exact.year}{source_suffix}"

    lower = _nearest_record(records, score, prefer_lower=True)
    higher = _nearest_record(records, score, prefer_lower=False)
    nearest = min(records, key=lambda item: abs(item.score - score))

    if lower and higher and lower.score != higher.score:
        estimated = _interpolate_rank(lower, higher, score)
        source_type = lower.source_type or higher.source_type
        source_suffix = f":{source_type}" if source_type else ""
        return estimated, f"estimated_from_score_interpolated:{lower.year}{source_suffix}"

    source_suffix = f":{nearest.source_type}" if nearest.source_type else ""
    return nearest.rank, f"estimated_from_nearest_score:{nearest.year}{source_suffix}"


def _rank_record_priority(item: ScoreRankRecord) -> tuple[int, int]:
    source_priority = {"exam_official": 0, "third_party": 2}.get(item.source_type, 1)
    return (source_priority, -item.year)


def _nearest_record(records: List[ScoreRankRecord], score: int, prefer_lower: bool) -> ScoreRankRecord | None:
    if prefer_lower:
        candidates = [item for item in records if item.score <= score]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.score)

    candidates = [item for item in records if item.score >= score]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item.score)


def _interpolate_rank(lower: ScoreRankRecord, higher: ScoreRankRecord, score: int) -> int:
    score_span = higher.score - lower.score
    rank_span = higher.rank - lower.rank
    ratio = (score - lower.score) / score_span
    return round(lower.rank + rank_span * ratio)


def build_profile(payload: Dict[str, str]) -> StudentProfile:
    raw_province = payload["province"].strip()
    province = raw_province
    normalized_notes: List[str] = []
    preferred_regions = parse_keywords(payload.get("preferred_regions", ""))
    city_registry = _load_city_province_registry()
    if raw_province not in PROVINCES and raw_province in city_registry:
        province = city_registry[raw_province]
        if raw_province not in preferred_regions:
            preferred_regions.append(raw_province)
        normalized_notes.append(f"已将省份栏中的城市“{raw_province}”归一为省份“{province}”，并加入城市偏好。")

    subject_type, subject_note = _normalize_subject_type(province, payload["subject_type"].strip())
    if subject_note:
        normalized_notes.append(subject_note)
    score = _parse_int(payload.get("score"))
    rank = _parse_int(payload.get("rank"))
    rank_source = "manual"

    if rank is None and score is not None:
        rank, rank_source = estimate_rank(province, subject_type, score)

    return StudentProfile(
        province=province,
        subject_type=subject_type,
        score=score,
        rank=rank,
        rank_source=rank_source,
        preferred_majors=parse_keywords(payload.get("preferred_majors", "")),
        excluded_majors=parse_keywords(payload.get("excluded_majors", "")),
        preferred_regions=preferred_regions,
        career_goal=payload.get("career_goal", "").strip(),
        family_background=payload.get("family_background", "").strip(),
        accept_postgraduate=payload.get("accept_postgraduate", "").strip().lower() in {"y", "yes", "true", "1"},
        parent_expectation=payload.get("parent_expectation", "").strip(),
        student_expectation=payload.get("student_expectation", "").strip(),
        city_priority=payload.get("city_priority", "").strip(),
        school_priority=payload.get("school_priority", "").strip(),
        major_priority=payload.get("major_priority", "").strip(),
        stability_priority=payload.get("stability_priority", "").strip(),
        salary_priority=payload.get("salary_priority", "").strip(),
        postgraduate_priority=payload.get("postgraduate_priority", "").strip(),
        normalized_notes=normalized_notes,
    )


def generate_recommendations(payload: Dict[str, str]) -> List[Recommendation]:
    profile = build_profile(payload)
    records = load_admission_records(profile)
    return recommend(records, profile)


def generate_recommendation_response(payload: Dict[str, str]) -> tuple[StudentProfile, List[Recommendation], dict[str, object]]:
    profile = build_profile(payload)
    records = load_admission_records(profile)
    recommendations = recommend(records, profile)
    diagnostics = build_recommendation_diagnostics(profile, records, recommendations)
    return profile, recommendations, diagnostics


def render_summary(
    profile: StudentProfile,
    recommendations: List[Recommendation],
    diagnostics: dict[str, object] | None = None,
) -> str:
    rank_text = f"位次{profile.rank}" if profile.rank is not None else "位次未匹配"
    if profile.rank_source.startswith("estimated_from_score"):
        rank_text += "（按分数自动估算）"
    elif profile.rank_source == "missing_score_rank_table":
        rank_text += "（当前没有对应省份/科类的一分一段表）"

    lines = [
        f"考生画像：{profile.province} / {profile.subject_type} / {profile.score or '未填'}分 / {rank_text}",
        f"偏好专业：{', '.join(profile.preferred_majors) if profile.preferred_majors else '未明确'}",
        f"核心诉求：{profile.career_goal or '未明确'}",
        f"家庭资源：{profile.family_background or '未明确'}",
        f"数据模式：{'学峰真实录取库优先' if has_real_admission_db() else '本地样例数据'}",
        "",
    ]

    if profile.normalized_notes:
        lines.append("输入归一化：")
        for note in profile.normalized_notes:
            lines.append(f"- {note}")
        lines.append("")

    if profile.rank_source.startswith("estimated_from"):
        if "third_party" in profile.rank_source:
            lines.append("位次说明：当前位次来自第三方整理的一分一段表，已用于初筛，正式填报前必须用省教育考试院原表复核。")
        elif "exam_official" in profile.rank_source:
            lines.append("位次说明：当前位次来自省级教育考试院官方分数分布/一分一段数据，已用于初筛。")
        else:
            lines.append("位次说明：当前位次来自本地一分一段表，正式使用时应替换或复核为对应省份当年官方数据。")
        lines.append("")

    if diagnostics:
        lines.append(render_diagnostics(diagnostics))
        lines.append("")

    lines.append(render_research_plan(profile, [item.school_name for item in recommendations]))
    lines.append("")

    if not recommendations:
        if profile.preferred_majors:
            lines.append(
                "当前没有按你填写的专业方向筛到合适结果。系统没有自动切换到其他热门专业；建议放宽专业关键词、城市限制，或补充该方向的录取数据后再查。"
            )
        else:
            lines.append("当前没有筛到合适结果。建议放宽城市关键词，或改用更宽的位次窗口再查。")
        return "\n".join(lines)

    reference_count = sum(
        1
        for item in recommendations
        if "外省生源数据" in item.risk or "生源省份参考" in item.reason
    )
    if reference_count:
        lines.append(
            f"数据提示：当前{profile.province}本省可用录取线不足，已补充{reference_count}条外省同分段参考候选。外省参考只用于扩大学校视野，不能直接当作{profile.province}正式冲稳保依据。"
        )
        lines.append("")

    current_tier = ""
    for item in recommendations:
        if item.tier != current_tier:
            current_tier = item.tier
            lines.append(f"{current_tier}档：")
        rank_text = f"位次{item.min_rank}" if item.min_rank else "位次未可靠入库"
        lines.append(
            f"- {item.school_name} · {item.major_name} · {item.city or '城市待核'} · {item.year}年 · 最低{item.min_score}分 · {rank_text} · 匹配分{item.fit_score}"
        )
        lines.append(f"  理由：{item.reason}")
        lines.append(f"  风险：{item.risk}")
    lines.append("")
    lines.append("提醒：具体数字优先看真实录取库和联网取证结果，最终仍以省考试院官方投档表和学校招生章程为准。")
    return "\n".join(lines)
