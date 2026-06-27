from __future__ import annotations

from typing import Iterable, List

from .models import AdmissionRecord, Recommendation, StudentProfile


RANK_TIER_RULES = (
    ("冲", -15000, -1000),
    ("稳", -1000, 6000),
    ("保", 6000, 30000),
)

SCORE_TIER_RULES = (
    ("冲", 6, 20),
    ("稳", -5, 5),
    ("保", -20, -6),
)
TIER_RISK_ORDER = {"冲": 0, "稳": 1, "保": 2}
SPECIAL_ADMISSION_KEYWORDS = (
    "提前批",
    "本科提前批",
    "高校专项",
    "国家专项",
    "地方专项",
    "优师计划",
    "公费师范",
    "艺术类",
    "体育类",
)

DISCOURAGED_MAJORS = {
    "土木": "土木行业下行，普通家庭慎选，除非分数段只能先解决本科。",
    "建筑": "建筑市场不景气，回报周期长。",
    "材料": "材料本科就业不友好，通常要读研读博。",
    "化工": "化工对口岗位环境和地域限制较多。",
    "生物": "生物本科就业弱，深造压力大。",
    "环境": "环境类岗位多但收入弹性有限。",
    "市场营销": "专业壁垒低，普通家庭不优先。",
    "工商管理": "没有家业或资源，不建议本科直接读纯管理。",
    "金融": "金融吃学校层次和家庭资源，普通家庭慎选。",
    "英语": "基础外语被 AI 冲击，除非顶尖外语院校。",
    "新闻": "传统媒体收缩，普通家庭慎选。",
}

STRONG_MAJOR_TAGS = {
    "计算机": ("计算机", "软件", "人工智能", "数据科学", "信息安全", "网络工程"),
    "电子": ("电子", "通信", "微电子", "集成电路", "光电"),
    "电气": ("电气", "能源", "智能电网"),
    "自动化": ("自动化", "机器人工程", "控制"),
    "法学": ("法学",),
    "汉语言": ("汉语言", "中文"),
    "会计": ("会计", "财务", "审计"),
    "师范": ("师范", "教育"),
    "医学": ("临床", "口腔", "医学", "麻醉", "影像"),
}

RESOURCE_MATCHES = {
    "电力": ("电气", "能源", "三峡大学", "华北电力", "东北电力", "上海电力"),
    "电网": ("电气", "能源", "三峡大学", "华北电力", "东北电力", "上海电力"),
    "铁路": ("交通", "轨道", "铁道", "西南交通", "北京交通", "石家庄铁道", "大连交通"),
    "医生": ("临床", "口腔", "医学", "护理", "药学"),
    "医疗": ("临床", "口腔", "医学", "护理", "药学"),
    "教师": ("师范", "汉语言", "数学", "英语", "教育"),
    "老师": ("师范", "汉语言", "数学", "英语", "教育"),
}


def filter_records(records: Iterable[AdmissionRecord], profile: StudentProfile) -> List[AdmissionRecord]:
    filtered: List[AdmissionRecord] = []
    preferred_regions = [item for item in profile.preferred_regions if item not in {"不限", "不限城市", "全国", "都可以"}]
    for record in records:
        if record.province and profile.province and profile.province not in record.province:
            continue
        if preferred_regions and record.city not in preferred_regions:
            continue
        if profile.excluded_majors and any(keyword in record.major_name for keyword in profile.excluded_majors):
            continue
        filtered.append(record)
    return filtered


def decide_tier(profile: StudentProfile, record: AdmissionRecord) -> str | None:
    rank_tier = None
    if profile.rank is not None and record.min_rank:
        rank_delta = record.min_rank - profile.rank
        for tier, low, high in RANK_TIER_RULES:
            if low <= rank_delta <= high:
                rank_tier = tier
                break

    score_tier = None
    if profile.score is not None and record.min_score:
        score_delta = record.min_score - profile.score
        for tier, low, high in SCORE_TIER_RULES:
            if low <= score_delta <= high:
                score_tier = tier
                break

    if rank_tier and profile.score is not None and record.min_score:
        score_tier = score_tier or _broad_score_tier(profile.score, record.min_score)

    tiers = [tier for tier in (rank_tier, score_tier) if tier]
    if not tiers:
        return None
    return min(tiers, key=lambda tier: TIER_RISK_ORDER[tier])


def decide_display_tier(profile: StudentProfile, record: AdmissionRecord) -> str | None:
    if _is_low_confidence_reference(record):
        return "参考"
    if _is_special_admission_record(record):
        return "参考"
    return decide_tier(profile, record) or "参考"


def _broad_score_tier(profile_score: int, record_score: int) -> str:
    score_delta = record_score - profile_score
    if score_delta >= 6:
        return "冲"
    if score_delta >= -5:
        return "稳"
    return "保"


def _is_special_admission_record(record: AdmissionRecord) -> bool:
    text = f"{record.major_name}{record.source}"
    return any(keyword in text for keyword in SPECIAL_ADMISSION_KEYWORDS)


def _is_low_confidence_reference(record: AdmissionRecord) -> bool:
    return "confidence=low" in record.source or "低置信院校层参考" in record.source


def score_record(profile: StudentProfile, record: AdmissionRecord, tier: str) -> tuple[float, List[str]]:
    score = 60.0
    breakdown: List[str] = ["基础匹配 60"]

    if profile.rank is not None and record.min_rank:
        distance = abs(profile.rank - record.min_rank)
        rank_adjustment = max(0.0, 22.0 - distance / 1200.0)
        score += rank_adjustment
        breakdown.append(f"位次接近 +{rank_adjustment:.1f}")

    if profile.score is not None and record.min_score:
        distance = abs(profile.score - record.min_score)
        score_adjustment = max(0.0, 12.0 - distance * 0.8)
        score += score_adjustment
        breakdown.append(f"分数接近 +{score_adjustment:.1f}")

    major_bonus = _major_match_bonus(profile, record)
    if major_bonus:
        score += major_bonus
        breakdown.append(f"专业方向匹配 +{major_bonus:.1f}")

    resource_bonus = _resource_match_bonus(profile, record)
    if resource_bonus:
        score += resource_bonus
        breakdown.append(f"家庭资源对口 +{resource_bonus:.1f}")

    goal_bonus = _goal_match_bonus(profile, record)
    if goal_bonus:
        score += goal_bonus
        breakdown.append(f"核心诉求匹配 +{goal_bonus:.1f}")

    school_bonus = _school_level_bonus(record)
    if school_bonus:
        score += school_bonus
        breakdown.append(f"学校层级 +{school_bonus:.1f}")

    penalty, reason = _discouraged_penalty(record)
    if penalty:
        score -= penalty
        breakdown.append(f"{reason} -{penalty:.1f}")

    if tier == "保":
        score += 4
        breakdown.append("保底安全性 +4.0")
    elif tier == "冲":
        score -= 2
        breakdown.append("冲刺不确定性 -2.0")
    elif tier == "参考":
        score -= 8
        breakdown.append("超出常规冲稳保窗口 -8.0")

    return round(score, 1), breakdown


def build_reason(profile: StudentProfile, record: AdmissionRecord, tier: str, breakdown: List[str]) -> str:
    rank_text = f"位次{record.min_rank}" if record.min_rank else "位次未可靠入库"
    parts = [
        f"{record.school_name}的{record.major_name}，{record.year}年最低{record.min_score}分、{rank_text}。"
    ]
    if record.source:
        parts.append(f"数据来源：{record.source}。")
    if _major_match_bonus(profile, record):
        parts.append("专业方向和你的偏好比较贴。")
    if _resource_match_bonus(profile, record):
        parts.append("这个方向能吃到家庭资源或行业资源。")
    if profile.career_goal:
        parts.append(f"按你偏向“{profile.career_goal}”的诉求，它有一定匹配度。")
    parts.append(f"综合分档放在“{tier}”。")
    parts.append("评分依据：" + "；".join(breakdown[:5]) + "。")
    return "".join(parts)


def build_risk(profile: StudentProfile, record: AdmissionRecord, tier: str) -> str:
    risk_parts: List[str] = []
    if _is_low_confidence_reference(record):
        risk_parts.append("这条是低置信院校层参考，缺少专业组或选科精确口径，只用于补充学校视野，不能直接作为正式志愿梯度依据。")
    if record.source.startswith("third_party:baidunetdisk_2026_gaokao_pack"):
        risk_parts.append("这条2025最低分位来自第三方整理包，已用于补充覆盖，正式填报前必须用省教育考试院官方投档表抽样复核。")
    if "非" in record.source and "生源省份参考" in record.source:
        risk_parts.append(f"这条使用的是外省生源数据，不是{profile.province}考生的正式投档线，只能作城市院校参考。")
    if "暂无本地分数线" in record.source:
        risk_parts.append(f"当前缺少{profile.province}生源对应{record.city or '该城市'}院校的本地录取线，需补库或联网复核。")
    if "rank_missing=true" in record.source:
        risk_parts.append("这条官方表只提供投档最低分，未提供最低位次；当前不能按位次精确排序，只能作分数层面的初筛参考。")
    if _is_special_admission_record(record):
        risk_parts.append("这条属于提前批、专项计划、优师/公费师范、艺术体育等特殊口径，默认只作参考；只有确认资格、批次和报考意愿后才能放入正式志愿梯度。")
    if profile.rank is not None and record.min_rank:
        rank_delta = record.min_rank - profile.rank
        if rank_delta < 0:
            risk_parts.append(f"往年位次比你高约{abs(rank_delta)}名。")
        else:
            risk_parts.append(f"往年位次比你宽松约{rank_delta}名。")
    if profile.score is not None and record.min_score:
        score_delta = record.min_score - profile.score
        if score_delta > 0:
            risk_parts.append(f"往年最低分高你{score_delta}分。")
        elif score_delta < 0:
            risk_parts.append(f"往年最低分低你{abs(score_delta)}分。")
    if tier == "冲":
        risk_parts.append("冲档只适合你能接受专业调剂或专业组内冷门专业的情况。")
    elif tier == "稳":
        risk_parts.append("稳档也要看今年招生计划和专业组变化。")
    elif tier == "保":
        risk_parts.append("保底学校不能只看学校名，要确认专业能接受。")
    else:
        risk_parts.append("该项超出当前冲稳保窗口，仅作为目标城市候选参考。")
    penalty, reason = _discouraged_penalty(record)
    if penalty:
        risk_parts.append(reason)
    risk_parts.append("最终以省考试院投档表和学校招生章程为准。")
    return "".join(risk_parts)


def recommend(records: Iterable[AdmissionRecord], profile: StudentProfile, limit_per_tier: int = 5) -> List[Recommendation]:
    if profile.rank is None and profile.score is None:
        raise ValueError("请至少提供分数或位次。")

    candidates = filter_records(records, profile)
    grouped: dict[str, List[Recommendation]] = {"冲": [], "稳": [], "保": [], "参考": []}

    for record in candidates:
        tier = decide_display_tier(profile, record)
        if not tier:
            continue
        fit_score, breakdown = score_record(profile, record, tier)
        grouped[tier].append(
            Recommendation(
                school_name=record.school_name,
                major_name=record.major_name,
                city=record.city,
                year=record.year,
                min_score=record.min_score,
                min_rank=record.min_rank,
                tier=tier,
                fit_score=fit_score,
                reason=build_reason(profile, record, tier, breakdown),
                risk=build_risk(profile, record, tier),
                score_breakdown=breakdown,
            )
        )

    results: List[Recommendation] = []
    for tier in ("冲", "稳", "保", "参考"):
        ranked = sorted(grouped[tier], key=lambda item: _recommendation_sort_key(item, profile))
        results.extend(_dedup_recommendations(ranked)[:limit_per_tier])
    if profile.preferred_regions and len(results) < len(profile.preferred_regions) * 4:
        results = _ensure_city_reference_minimum(grouped, results, profile.preferred_regions, minimum_per_city=4)
    return results


def _recommendation_sort_key(item: Recommendation, profile: StudentProfile) -> tuple[float, ...]:
    rank_key = item.min_rank or 99999999
    rank_quality = 0 if item.min_rank else 1
    score_delta = item.min_score - profile.score if profile.score is not None and item.min_score else 0
    if item.tier == "冲":
        return (rank_quality, -score_delta, -item.fit_score, rank_key)
    if item.tier == "稳":
        return (rank_quality, -item.fit_score, abs(score_delta), rank_key)
    if item.tier == "保":
        return (rank_quality, -item.fit_score, score_delta, rank_key)
    return (rank_quality, -item.fit_score, rank_key)


def _ensure_city_reference_minimum(
    grouped: dict[str, List[Recommendation]],
    results: List[Recommendation],
    preferred_regions: List[str],
    minimum_per_city: int,
) -> List[Recommendation]:
    seen = {(item.school_name, item.major_name, item.city) for item in results}
    by_city = {city: sum(1 for item in results if item.city == city) for city in preferred_regions}
    all_candidates: List[Recommendation] = []
    for tier in ("冲", "稳", "保", "参考"):
        all_candidates.extend(sorted(grouped[tier], key=lambda item: (-item.fit_score, item.min_rank or 99999999)))

    for city in preferred_regions:
        for item in all_candidates:
            if by_city.get(city, 0) >= minimum_per_city:
                break
            key = (item.school_name, item.major_name, item.city)
            if item.city != city or key in seen:
                continue
            results.append(item)
            seen.add(key)
            by_city[city] = by_city.get(city, 0) + 1
    return results


def _dedup_recommendations(items: List[Recommendation], max_per_school: int = 2) -> List[Recommendation]:
    seen: set[tuple[str, str]] = set()
    school_counts: dict[str, int] = {}
    result: List[Recommendation] = []
    for item in items:
        key = (item.school_name, item.major_name)
        if key in seen:
            continue
        if school_counts.get(item.school_name, 0) >= max_per_school:
            continue
        seen.add(key)
        school_counts[item.school_name] = school_counts.get(item.school_name, 0) + 1
        result.append(item)
    return result


def _major_match_bonus(profile: StudentProfile, record: AdmissionRecord) -> float:
    text = record.major_name
    bonus = 0.0
    for preferred in profile.preferred_majors:
        expanded = STRONG_MAJOR_TAGS.get(preferred, (preferred,))
        if any(keyword in text for keyword in expanded):
            bonus = max(bonus, 18.0)
    return bonus


def _resource_match_bonus(profile: StudentProfile, record: AdmissionRecord) -> float:
    family = profile.family_background
    if not family or family in {"普通家庭", "没资源", "无"}:
        return 0.0
    text = f"{record.school_name}{record.major_name}{''.join(record.tags)}"
    for key, keywords in RESOURCE_MATCHES.items():
        if key in family and any(keyword in text for keyword in keywords):
            return 12.0
    return 0.0


def _goal_match_bonus(profile: StudentProfile, record: AdmissionRecord) -> float:
    goal = profile.career_goal
    text = f"{record.major_name}{''.join(record.tags)}"
    if not goal:
        return 0.0
    if any(token in goal for token in ("就业", "高薪", "赚钱")) and any(
        token in text for token in ("计算机", "软件", "电子", "电气", "自动化", "口腔")
    ):
        return 10.0
    if any(token in goal for token in ("稳定", "国企", "电网")) and any(
        token in text for token in ("电气", "能源", "自动化", "交通", "医学", "师范")
    ):
        return 10.0
    if "考公" in goal and any(token in text for token in ("法学", "汉语言", "会计", "财务", "计算机")):
        return 10.0
    if "考研" in goal and any(token in text for token in ("数学", "电子", "计算机", "医学", "自动化")):
        return 8.0
    return 0.0


def _school_level_bonus(record: AdmissionRecord) -> float:
    level = record.school_level
    if "985" in level:
        return 10.0
    if "211" in level or "双一流" in level:
        return 7.0
    if "省重点" in level:
        return 3.0
    return 0.0


def _discouraged_penalty(record: AdmissionRecord) -> tuple[float, str]:
    for keyword, reason in DISCOURAGED_MAJORS.items():
        if keyword in record.major_name:
            return 12.0, reason
    return 0.0, ""
