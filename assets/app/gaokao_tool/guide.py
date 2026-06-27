from __future__ import annotations

import re
from typing import Any, Dict, List

from .service import generate_recommendations


SLOTS = [
    "province",
    "subject_type",
    "score",
    "rank",
    "preferred_majors",
    "excluded_majors",
    "preferred_regions",
    "career_goal",
    "parent_expectation",
    "student_expectation",
    "accept_postgraduate",
    "family_background",
    "rank_unknown",
]


def initial_guide_state() -> Dict[str, Any]:
    return {
        "payload": {},
        "stage": "basic",
        "messages": [
            {
                "role": "advisor",
                "text": "咱们先别急着报学校，我先帮孩子定个位。孩子是哪个省的？今年大概多少分？",
                "options": [],
            }
        ],
    }


def next_guide_turn(state: Dict[str, Any], user_text: str = "", option: str = "") -> Dict[str, Any]:
    payload = dict(state.get("payload") or {})
    messages = list(state.get("messages") or [])

    if user_text or option:
        answer = (option or user_text).strip()
        messages.append({"role": "parent", "text": answer, "options": []})
        _merge_answer(payload, answer)

    stage = _decide_stage(payload)
    advisor_message = _build_advisor_message(stage, payload)
    messages.append(advisor_message)

    response = {
        "payload": payload,
        "stage": stage,
        "messages": messages,
        "ready": stage == "ready",
        "profile_summary": _profile_summary(payload),
        "missing": _missing_slots(payload),
    }

    if stage == "ready":
        try:
            recommendations = generate_recommendations(_recommend_payload(payload))
            response["recommendations"] = [item.__dict__ for item in recommendations]
        except (KeyError, TypeError, ValueError) as exc:
            response["recommendation_error"] = str(exc)

    return response


def _merge_answer(payload: Dict[str, str], answer: str) -> None:
    text = answer.strip()
    if not text:
        return

    province = _find_province(text)
    if province:
        if not payload.get("province") or _looks_like_basic_identity_answer(text):
            payload["province"] = province

    subject = _find_subject_type(text)
    if subject:
        payload["subject_type"] = subject

    score = _find_score(text)
    if score:
        payload["score"] = score

    rank = _find_rank(text)
    if rank:
        payload["rank"] = rank
        payload.pop("rank_unknown", None)
    elif _is_unknown_rank_answer(text):
        payload["rank_unknown"] = "y"

    has_employment_goal = any(token in text for token in ("就业", "工作", "高薪", "赚钱"))
    has_postgraduate_goal = any(token in text for token in ("考研", "保研", "深造", "读研", "升学"))
    if has_employment_goal:
        payload["career_goal"] = "就业"
    if any(token in text for token in ("考公", "公务员", "编制", "体制")):
        payload["career_goal"] = "考公"
    if has_postgraduate_goal:
        payload["career_goal"] = "升学就业兼顾" if has_employment_goal else "考研深造"
        payload["accept_postgraduate"] = "y"
    if any(token in text for token in ("211", "双一流", "名校", "学校牌子", "学校名气")):
        payload["school_priority"] = "学校层级优先"

    if any(token in text for token in ("不考研", "不读研", "本科就业")):
        payload["accept_postgraduate"] = "n"
    elif any(token in text for token in ("接受考研", "可以考研", "愿意读研", "能读研")):
        payload["accept_postgraduate"] = "y"

    majors = _extract_after_markers(text, ("想学", "喜欢", "专业", "方向"))
    if majors and "不" not in text[: max(text.find(majors), 0)]:
        payload["preferred_majors"] = majors
    elif _likes_broad_science_major(text):
        payload["preferred_majors"] = "理工技术类"

    excluded = _extract_excluded_majors(text)
    if excluded:
        payload["excluded_majors"] = excluded

    regions = _extract_regions(text)
    if regions:
        payload["preferred_regions"] = regions

    if any(token in text for token in ("普通家庭", "没资源", "无资源")):
        payload["family_background"] = "普通家庭"
    elif any(token in text for token in ("电网", "医生", "医疗", "老师", "教师", "铁路", "公务员")):
        payload["family_background"] = text

    if any(token in text for token in ("家长", "父母", "我们希望")):
        payload["parent_expectation"] = text
    if any(token in text for token in ("孩子想", "孩子喜欢", "他想", "她想")):
        payload["student_expectation"] = text


def _decide_stage(payload: Dict[str, str]) -> str:
    if not payload.get("province") or not payload.get("subject_type") or not payload.get("score"):
        return "basic"
    if not payload.get("rank") and payload.get("rank_unknown") != "y":
        return "rank"
    if not payload.get("career_goal"):
        return "goal"
    if not payload.get("preferred_majors") and not payload.get("excluded_majors"):
        return "major"
    if not payload.get("preferred_regions"):
        return "region"
    if "考研" in payload.get("career_goal", "") and not payload.get("accept_postgraduate"):
        return "postgraduate"
    if not payload.get("family_background"):
        return "family"
    return "ready"


def _build_advisor_message(stage: str, payload: Dict[str, str]) -> Dict[str, Any]:
    summary = _profile_summary(payload)
    if stage == "basic":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n我先把最基础的省份、选科和分数记下来。孩子是哪一类选科？比如物化生、物化技、历史类这种。",
            "options": ["物化技", "物化生", "历史类"],
        }
    if stage == "rank":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n现在先补一个最关键的信息：孩子位次大概是多少？如果还没查到，说不知道也行。",
            "options": ["位次6万左右", "还不知道位次", "我只知道分数"],
        }
    if stage == "goal":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n先不急着看学校。咱们先定一个大方向：更想本科毕业好就业，还是愿意为后面考研/升学做准备？",
            "options": ["本科就业优先", "想升学/考研", "还没想清楚"],
        }
    if stage == "major":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n那专业方向就很重要了。孩子有没有比较喜欢的方向？先说喜欢的就行，排斥项我们后面再慢慢排。",
            "options": ["喜欢电子信息类", "喜欢计算机类", "暂时没目标"],
        }
    if stage == "region":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n那我再问一句现实的：为了学校层次，外省远一点能接受吗？",
            "options": ["可以接受远一点", "尽量浙江/长三角", "地方无所谓"],
        }
    if stage == "postgraduate":
        return {
            "role": "advisor",
            "text": f"{_human_response(payload)}\n那我按升学路线来想。孩子能接受本科后继续考研吗？",
            "options": ["可以接受考研", "最好本科就业", "保研机会很重要"],
        }
    if stage == "family":
        return {
            "role": "advisor",
            "text": f"{_family_stage_response(payload)}\n最后补一句现实条件：家里有没有明显行业资源？没有也没关系，普通家庭我会更看重专业确定性。",
            "options": ["普通家庭，没有资源", "有电网/电力资源", "有医疗/教师资源"],
        }
    return {
        "role": "advisor",
            "text": f"{_human_response(payload)}\n信息差不多够了。我先给你讲几条路，不会一次定死；你听完觉得哪条不舒服，我们再收紧。",
        "options": ["生成第一版冲稳保", "我想先改目标", "我想补充排斥项"],
    }


def _profile_summary(payload: Dict[str, str]) -> str:
    known = []
    if payload.get("province"):
        known.append(payload["province"])
    if payload.get("subject_type"):
        known.append(payload["subject_type"])
    if payload.get("score"):
        known.append(f"{payload['score']}分")
    if payload.get("rank"):
        known.append(f"位次{payload['rank']}")
    if payload.get("career_goal"):
        known.append(f"目标：{payload['career_goal']}")
    if payload.get("preferred_majors"):
        known.append(f"想看：{payload['preferred_majors']}")
    if payload.get("preferred_regions"):
        known.append(f"地区：{payload['preferred_regions']}")
    if not known:
        return "目前画像：还没有关键信息。"
    return "目前画像：" + " / ".join(known)


def _human_response(payload: Dict[str, str]) -> str:
    province = payload.get("province", "")
    subject = payload.get("subject_type", "")
    score = payload.get("score", "")
    rank = payload.get("rank", "")
    goal = payload.get("career_goal", "")
    majors = payload.get("preferred_majors", "")

    if rank and not goal:
        return f"位次{rank}左右就清楚多了，这个位置可以做一套比较像样的冲稳保，也有机会往更好的学校层次够一够。"
    if payload.get("rank_unknown") == "y" and not goal:
        return "位次不记得没关系，咱先按分数做粗判断，后面真正排志愿时再用一分一段表补上。"
    if "兼顾" in goal:
        if not majors:
            return "想升学又兼顾就业，这个思路挺稳。我们不能只追学校名，也不能只看专业热不热，要找学校平台和技术专业之间的平衡。"
        return f"那就有方向了。{majors}可以看，后面我会按学校平台和就业专业两边一起筛。"
    if "考研" in goal or "升学" in goal:
        if not majors:
            return "想升学的话，思路就变了：别只看专业名字热不热门，学校平台和学习氛围也很重要。"
        return f"那就有方向了。{majors}可以看，但不用把自己卡太死，后面可以围绕技术大类去挑更好的学校。"
    if "就业" in goal:
        return "就业优先的话，就不能只追学校名头，要看专业强度、城市产业和校招认可度。"
    if majors:
        return f"{majors}这个方向比较适合按专业组和学科实力细筛，不能只看学校名字。"
    if province and score and not rank:
        if province == "江苏" and "物理" in subject:
            return (
                f"咱孩子江苏物理{score}分，这个分数是有选择空间的。稳妥看较好的公办本科、省重点、行业特色院校里的合适专业组；"
                "往上冲可以看双一流边缘或强校相对冷一点的专业组。顶尖211可能有点勉强，不是完全不能看，但要按位次和专业组细查。"
            )
        if province == "浙江":
            return f"{province}{score}分，这个成绩不差，已经能看不少不错的公办本科；但浙江一定要按位次判断，不能只看分。"
        return f"{province}{score}分，这个分数不低了，后面不是随便保个本科的问题，是可以认真挑学校层次和专业方向的。"
    return _profile_summary(payload)


def _family_stage_response(payload: Dict[str, str]) -> str:
    regions = payload.get("preferred_regions", "")
    goal = payload.get("career_goal", "")
    if "沿海" in regions:
        if "升学" in goal:
            return "沿海这个要求可以保留，但咱要心里有数：沿海机会和环境更好，同样分数下学校牌子可能会比中西部吃亏一点。所以后面我会拿沿海学校和平台更强的外省学校做对照，让你们看清楚值不值。"
        return "沿海这个想法挺实际，实习和找工作机会会多一些；代价是同样分数下学校层次可能没那么占便宜。"
    return _human_response(payload)


def _missing_slots(payload: Dict[str, str]) -> List[str]:
    missing = []
    for key in ("province", "subject_type", "score", "career_goal", "preferred_majors", "preferred_regions"):
        if not payload.get(key):
            missing.append(key)
    return missing


def _recommend_payload(payload: Dict[str, str]) -> Dict[str, str]:
    data = {key: payload.get(key, "") for key in SLOTS}
    if "接受" in data.get("accept_postgraduate", "") or data.get("accept_postgraduate") == "y":
        data["accept_postgraduate"] = "y"
    return data


def _find_province(text: str) -> str:
    provinces = (
        "北京 上海 天津 重庆 河北 山西 辽宁 吉林 黑龙江 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 海南 四川 贵州 云南 陕西 甘肃 青海 台湾 内蒙古 广西 西藏 宁夏 新疆 香港 澳门"
    ).split()
    return next((item for item in provinces if item in text), "")


def _looks_like_basic_identity_answer(text: str) -> bool:
    return any(token in text for token in ("省", "考生", "孩子", "高考", "物理", "历史", "物化", "理科", "文科", "分"))


def _find_subject_type(text: str) -> str:
    if any(token in text for token in ("物化生", "物化技", "物理", "理科")):
        return "物理类"
    if any(token in text for token in ("历史", "文科", "政史地")):
        return "历史类"
    if any(token in text for token in ("综合改革", "新高考综合", "普通类考生", "普通类")):
        return "普通类"
    return ""


def _find_score(text: str) -> str:
    match = re.search(r"(\d{3})\s*分?", text)
    if not match:
        return ""
    score = int(match.group(1))
    if 100 <= score <= 750:
        return str(score)
    return ""


def _find_rank(text: str) -> str:
    match = re.search(r"(?:位次|排名)\D*(\d{3,8})", text)
    if match:
        return match.group(1)

    wan_match = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
    if wan_match and any(token in text for token in ("位次", "排名", "左右", "大概", "约", "多")):
        return str(round(float(wan_match.group(1)) * 10000))

    chinese_wan = {
        "一万": "10000",
        "二万": "20000",
        "两万": "20000",
        "三万": "30000",
        "四万": "40000",
        "五万": "50000",
        "六万": "60000",
        "七万": "70000",
        "八万": "80000",
        "九万": "90000",
        "十万": "100000",
    }
    for key, value in chinese_wan.items():
        if key in text and any(token in text for token in ("位次", "排名", "左右", "大概", "约", "多")):
            return value
    return ""


def _is_unknown_rank_answer(text: str) -> bool:
    if any(token in text for token in ("不记得", "不太记得", "记不清", "不知道", "没查", "没看到", "忘了", "只知道分数")):
        return any(token in text for token in ("位次", "排名", "分数", "不记得", "不太记得", "记不清", "不知道", "没查", "忘了"))
    return False


def _extract_after_markers(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        if marker in text:
            tail = text.split(marker, 1)[1]
            tail = re.split(r"[。；;，,]", tail, 1)[0]
            return tail.strip("：: ")
    if any(token in text for token in ("计算机", "电子", "电气", "法学", "汉语言", "会计", "师范", "医学")):
        majors = [token for token in ("计算机", "电子信息", "电子", "电气", "法学", "汉语言", "会计", "师范", "医学") if token in text]
        return "、".join(dict.fromkeys(majors))
    return ""


def _likes_broad_science_major(text: str) -> bool:
    broad_major_tokens = ("理科专业都喜欢", "理工都可以", "工科都可以", "技术类都可以", "偏技术", "理科都行")
    return any(token in text for token in broad_major_tokens)


def _extract_excluded_majors(text: str) -> str:
    if not any(token in text for token in ("排斥", "不想", "不学", "不接受", "避开")):
        return ""
    majors = [token for token in ("土木", "建筑", "材料", "化工", "生物", "环境", "护理", "农学", "管理") if token in text]
    return "、".join(majors)


def _extract_regions(text: str) -> str:
    regions = []
    for token in ("杭州", "宁波", "上海", "武汉", "宜昌", "南京", "苏州", "广州", "深圳", "北京", "成都", "重庆", "西安"):
        if token in text:
            regions.append(token)
    if "本省" in text:
        regions.append("本省")
    if "省会" in text:
        regions.append("省会")
    if "长三角" in text:
        regions.append("长三角")
    if "珠三角" in text:
        regions.append("珠三角")
    if "沿海" in text:
        regions.append("沿海")
    if any(token in text for token in ("都可以", "不限", "全国", "无所谓", "不挑地方", "地方无所谓")):
        regions.append("不限")
    return "、".join(dict.fromkeys(regions))
