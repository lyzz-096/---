from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Recommendation, StudentProfile


REPORT_TEMPLATE_FILE = Path(__file__).resolve().parent.parent / "report_template" / "index.html"
REPORT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def build_report_data(
    profile: StudentProfile,
    recommendations: Iterable[Recommendation],
) -> dict[str, object]:
    items = list(recommendations)
    rank_text = f"{profile.rank} 位" if profile.rank is not None else "位次待核"
    score_text = f"{profile.score} 分" if profile.score is not None else "分数待核"
    preferred = "、".join(profile.preferred_majors) if profile.preferred_majors else "专业方向待进一步确认"
    excluded = "、".join(profile.excluded_majors) if profile.excluded_majors else "暂无明确排斥"
    regions = "、".join(profile.preferred_regions) if profile.preferred_regions else "地域暂不设硬限制"
    goal = profile.career_goal or "综合考虑"

    return {
        "studentProfile": {
            "province": profile.province or "省份待核",
            "subjectType": profile.subject_type or "科类/选科待核",
            "score": profile.score or 0,
            "rank": profile.rank or 0,
            "batch": "本科批",
            "positioning": (
                f"当前画像为{profile.province}、{profile.subject_type}、{score_text}、{rank_text}。"
                "本报告先按位次和家庭目标做初筛，正式填报前需回到省考试院计划书和高校招生网复核。"
            ),
            "coreTarget": f"本次核心目标：{goal}。偏好方向：{preferred}；排斥方向：{excluded}；地域偏好：{regions}。",
            "riskPreference": "风险偏好：均衡。冲刺学校保留少量，主方案优先保证公办、专业可接受和专业组风险可控。",
            "goals": [
                {"name": "专业匹配", "note": preferred},
                {"name": "地域偏好", "note": regions},
                {"name": "风险控制", "note": "专业组明细、学费、校区和特殊批次需逐项复核。"},
            ],
        },
        "strategySummary": {
            "explanation": "先用同省同科类位次建立候选池，再结合专业偏好、地域接受度、学校层次和风险偏好做冲稳保分层。",
            "priorities": [
                f"优先保留与“{preferred}”更接近的专业或专业组。",
                "优先公办本科和专业组明细清楚的学校。",
                "对家庭重点关注的学校，继续深挖它的行业标签、优势学院、学生项目、校招单位、升学平台和转专业政策。",
            ],
            "downgraded": [
                f"明确排斥或不感兴趣的方向降权：{excluded}。",
                "只查到专业组最低分但没有组内专业的学校，先标为待复核。",
                "第三方数据仅用于初筛，不替代官方计划书和投档结果。",
            ],
        },
        "recommendationTiers": [_recommendation_row(item, profile) for item in items],
        "schoolCards": [_school_card(item, profile, index) for index, item in enumerate(items, start=1)],
        "majorGroupRisks": _major_group_risks(items),
        "routeComparisons": _route_comparisons(profile, items),
        "checklist": [
            "省考试院招生计划书",
            "专业组包含专业",
            "当年招生人数变化",
            "近三年最低分和最低位次",
            "学费",
            "校区",
            "转专业政策",
            "保研 / 硕士点 / 升学情况",
            "就业质量报告",
            "体检限制",
            "中外合作或高收费说明",
            "单设志愿、地方专项、国家专项、优师计划等特殊批次",
        ],
        "sources": [
            {"type": "官方来源", "note": "省考试院招生计划书、投档线、录取结果查询。正式填报以此为准。"},
            {"type": "学校官网", "note": "高校招生网、招生章程、学院介绍、就业质量报告、专业培养方案。"},
            {"type": "本地录取数据库", "note": "用于整理近年最低分、最低位次和候选池，需与官方数据互相校验。"},
            {"type": "辅助平台", "note": "仅作初筛参考，正式填报前需回到省考试院和高校招生网复核。"},
        ],
    }


def render_final_report_html(report_data: dict[str, object]) -> str:
    template = REPORT_TEMPLATE_FILE.read_text(encoding="utf-8")
    encoded = json.dumps(report_data, ensure_ascii=False, indent=6)
    replacement = f"const reportData = {encoded};"
    html, count = re.subn(
        r"const reportData = \{.*?\n    \};",
        replacement,
        template,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("最终报告模板中没有找到 const reportData 数据块。")
    return html


def export_final_report(
    profile: StudentProfile,
    recommendations: Iterable[Recommendation],
    output_dir: Path | None = None,
) -> Path:
    report_data = build_report_data(profile, recommendations)
    html = render_final_report_html(report_data)
    target_dir = output_dir or REPORT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / suggest_report_filename(profile)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def suggest_report_filename(profile: StudentProfile) -> str:
    parts = [
        _sanitize_filename_part(profile.province or "未知省份"),
        _sanitize_filename_part(str(profile.score) if profile.score is not None else "未知分数"),
        _sanitize_filename_part(profile.subject_type or "未知科类"),
        _sanitize_filename_part(profile.career_goal or "综合方向"),
        "高考志愿报告",
        datetime.now().strftime("%Y%m%d-%H%M%S"),
    ]
    return "_".join(part for part in parts if part) + ".html"


def _recommendation_row(item: Recommendation, profile: StudentProfile) -> dict[str, object]:
    rank_diff = "待核"
    if profile.rank is not None and item.min_rank:
        diff = item.min_rank - profile.rank
        rank_diff = f"{diff:+d}"
    return {
        "tier": item.tier,
        "school": item.school_name,
        "city": item.city or "城市待核",
        "majorGroup": item.major_name,
        "minScore": item.min_score or 0,
        "minRank": item.min_rank or 0,
        "rankDiff": rank_diff,
        "reason": item.reason,
        "risk": item.risk,
        "keyCandidate": "是" if item.tier in {"冲", "稳"} else "待定",
    }


def _school_card(item: Recommendation, profile: StudentProfile, index: int) -> dict[str, object]:
    return {
        "id": f"s{index}",
        "tier": item.tier,
        "feedback": "待确认",
        "name": item.school_name,
        "city": item.city or "城市待核",
        "tag": _school_tag(item),
        "why": f"这所学校进入候选，是因为它在{profile.province}同科类位次窗口内与当前画像有一定匹配。",
        "features": [
            f"先按“{_feature_probe_label(item)}”方向补查学校标签，重点看学院官网、专业培养方案、实验室或产业学院。",
            "继续核对就业质量报告、就业信息网和专场招聘，确认毕业出口是偏国企制造、信息软件、行业单位还是普通市场化岗位。",
            "如需列为重点候选，还要补查学生竞赛/项目、招生章程、转专业条件、推免或硕士点情况。",
        ],
        "majors": [_clean_major_group(item.major_name)],
        "data": [
            {
                "year": f"{item.year}",
                "minScore": item.min_score or 0,
                "minRank": item.min_rank or 0,
                "gap": _rank_gap_text(profile, item),
                "source": "本地录取数据库初筛",
            }
        ],
        "outcome": "就业和升学信息待复核。正式报告应补充学院硕士点、就业质量报告、典型招聘单位、学生项目和考研去向。",
        "risks": [
            item.risk,
            "需核对专业组内具体专业，不宜只看专业组最低分。",
            "最终以省考试院招生计划书和高校招生网为准。",
        ],
        "advice": f"暂放{item.tier}档候选；后续根据组内专业、学费、校区和家庭接受度决定是否保留。",
    }


def _major_group_risks(items: list[Recommendation]) -> list[dict[str, str]]:
    if not items:
        return [
            {
                "group": "专业组明细待复核",
                "contains": "暂无候选专业组",
                "likes": "待补充专业偏好",
                "accepts": "待定",
                "avoid": "待定",
                "transferRisk": "待复核",
                "feeRisk": "待复核",
                "campusRisk": "待复核",
                "physicalRisk": "待复核",
                "missingPlan": "需要先生成候选学校，再查省招生计划书和高校招生网。",
            }
        ]

    risks = []
    for item in items[:4]:
        risks.append(
            {
                "group": item.major_name,
                "contains": "组内专业需要以当年招生计划书为准。",
                "likes": "与考生偏好是否匹配待逐项标注。",
                "accepts": "可接受专业待进一步确认。",
                "avoid": "排斥专业和高风险专业待确认。",
                "transferRisk": "如果组内冷热专业差异大，调剂风险偏高。",
                "feeRisk": "需核对是否中外合作、高收费或特殊培养项目。",
                "campusRisk": "需核对校区和培养地点。",
                "physicalRisk": "化工、医学、食品等方向需核体检限制。",
                "missingPlan": "只查到最低分时不宜正式推荐，需补查组内专业。",
            }
        )
    return risks


def _route_comparisons(profile: StudentProfile, items: list[Recommendation]) -> list[dict[str, str]]:
    schools = "、".join(dict.fromkeys(item.school_name for item in items[:4])) or "候选学校待生成"
    return [
        {
            "name": "专业优先路线",
            "fit": "适合考生专业方向较明确、希望本科专业不要太偏的家庭。",
            "gain": "专业满意度和后续就业/考研方向更清楚。",
            "sacrifice": "可能接受学校名气或城市弱一点。",
            "recommend": schools,
            "risk": "需核对专业组里是否混入考生不接受的专业。",
        },
        {
            "name": "学校层次路线",
            "fit": "适合希望把学校平台尽量抬高、可以接受专业让步的家庭。",
            "gain": "学校平台和学习氛围可能更好。",
            "sacrifice": "热门专业可能进不去，专业组风险更高。",
            "recommend": schools,
            "risk": "冲刺学校不宜当作主稳方案。",
        },
        {
            "name": "城市优先路线",
            "fit": "适合对城市、距离和生活适应更敏感的家庭。",
            "gain": "生活适应和实习便利性更好。",
            "sacrifice": "同分数下专业和学校层次可能变窄。",
            "recommend": "结合地域偏好二次筛选。",
            "risk": "热门城市分数波动大，要留足保底。",
        },
        {
            "name": "公办稳妥路线",
            "fit": "适合更看重录取确定性、学费可控和家庭安心度的家庭。",
            "gain": "本科录取把握更高，费用风险更可控。",
            "sacrifice": "学校层次和城市资源可能不如冲刺方案。",
            "recommend": schools,
            "risk": "不宜为了稳而接受考生明显排斥的专业。",
        },
    ]


def _school_tag(item: Recommendation) -> str:
    parts = [item.city, item.major_name, f"{item.tier}档候选"]
    return " / ".join(part for part in parts if part)


def _feature_probe_label(item: Recommendation) -> str:
    text = f"{item.school_name} {item.major_name}"
    probes = [
        (("船舶", "海洋", "轮机", "航海"), "船舶海工、海洋装备和中船等行业出口"),
        (("电气", "电力", "能源"), "电力系统、能源企业和电气工程平台"),
        (("电子", "通信", "信息", "集成电路", "微电子"), "电子信息、通信、集成电路和电子设计竞赛"),
        (("计算机", "软件", "数据", "人工智能", "网络", "信息安全"), "计算机/软件学院、项目竞赛、软件园实习和硕士点"),
        (("自动化", "机器", "智能制造", "控制"), "自动化、机器人、智能车和工程训练项目"),
        (("交通", "轨道", "车辆"), "轨道交通、车辆工程和中车/铁路局招聘"),
        (("师范", "教育"), "师范认证、教育实习和教师招聘路径"),
        (("医学", "临床", "药", "护理", "影像", "检验"), "附属医院、实习医院、规培和学历门槛"),
    ]
    for keywords, label in probes:
        if any(keyword in text for keyword in keywords):
            return label
    return "学校行业背景、优势学院、竞赛项目、产业学院和校招单位"


def _clean_major_group(major_name: str) -> str:
    return major_name or "专业组明细待复核"


def _rank_gap_text(profile: StudentProfile, item: Recommendation) -> str:
    if profile.rank is None or not item.min_rank:
        return "位次差待核"
    diff = item.min_rank - profile.rank
    if diff > 0:
        return f"往年最低位次比考生宽松约 {diff} 位"
    if diff < 0:
        return f"往年最低位次比考生高约 {abs(diff)} 位"
    return "与考生位次基本一致"


def _sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "-", value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned or "未命名"
