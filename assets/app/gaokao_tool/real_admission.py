from __future__ import annotations

import os
import re
import sqlite3
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

from .models import AdmissionRecord, StudentProfile


DEFAULT_DB_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "data" / "admission_clean.db",
]
SCHOOL_CITY_REGISTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "school_city_registry.json"
LOW_CONFIDENCE_CANDIDATE_DB = (
    Path(__file__).resolve().parent.parent
    / ".runtime"
    / "resource_update"
    / "baidunetdisk_2025_admission_candidate_with_low_confidence.db"
)
LOW_CONFIDENCE_REFERENCE_PROVINCES = {"重庆", "贵州"}
SCORE_WINDOW = 20

VALID_SOURCE_KEYWORDS = (
    "投档线",
    "投档",
    "专业分数线",
    "分数线",
    "录取",
    "admission",
    "普通类",
    "第一段",
    "第二段",
    "本科批",
    "本科普通批",
    "普通批",
    "专科批",
    "提前批",
    "平行志愿",
)
NOISY_SOURCE_KEYWORDS = ("专业基本介绍", "知识库", "介绍")
BAD_SCHOOL_FRAGMENTS = ("就业方向", "发展前景", "专业要求", "本科就业", "薪酬最高", "职业概况")


def find_real_db_path() -> Path | None:
    env_path = os.environ.get("GAOKAO_ADMISSION_DB", "").strip()
    candidates = [Path(env_path)] if env_path else []
    candidates.extend(DEFAULT_DB_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def has_real_admission_db() -> bool:
    return find_real_db_path() is not None


def load_real_admission_records(profile: StudentProfile, limit: int = 240) -> List[AdmissionRecord]:
    db_path = find_real_db_path()
    if not db_path:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _query_rows(conn, profile, limit * 4)
    finally:
        conn.close()

    records = [_row_to_record(row) for row in rows if _is_valid_row(row) and _row_matches_subject(row, profile)]
    if profile.preferred_regions:
        records.extend(_load_city_reference_records(profile, limit))
        records.extend(_build_registry_city_reference_records(profile))
    if _should_load_low_confidence_reference(profile, records):
        records.extend(_load_low_confidence_reference_records(profile, limit * 2))
    if _distinct_school_count(records) < 4:
        records.extend(_load_national_reference_records(profile, limit))
    return _dedup_records(records)


def _distinct_school_count(records: List[AdmissionRecord]) -> int:
    return len({record.school_name for record in records})


def _should_load_low_confidence_reference(profile: StudentProfile, records: List[AdmissionRecord]) -> bool:
    if profile.province not in LOW_CONFIDENCE_REFERENCE_PROVINCES:
        return False
    if not LOW_CONFIDENCE_CANDIDATE_DB.exists():
        return False
    ranked_records = [record for record in records if record.year == 2025 and record.min_rank]
    return _distinct_school_count(ranked_records) < 8


def _load_low_confidence_reference_records(profile: StudentProfile, limit: int) -> List[AdmissionRecord]:
    if profile.province not in LOW_CONFIDENCE_REFERENCE_PROVINCES or not LOW_CONFIDENCE_CANDIDATE_DB.exists():
        return []

    conn = sqlite3.connect(str(LOW_CONFIDENCE_CANDIDATE_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = _query_low_confidence_reference_rows(conn, profile, limit)
    finally:
        conn.close()

    records: List[AdmissionRecord] = []
    for row in rows:
        if not _is_valid_row(row) or not _row_matches_subject(row, profile):
            continue
        record = _row_to_record(row)
        record.source = (
            f"{record.source}；低置信院校层参考；缺专业组/选科精确口径；"
            "不进入正式主库"
        )
        records.append(record)
    return records


def _query_low_confidence_reference_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    limit: int,
) -> List[sqlite3.Row]:
    conditions = [
        "province = ?",
        "year = 2025",
        "score IS NOT NULL",
        "score > 0",
        "rank IS NOT NULL",
        "rank > 0",
        "source LIKE '%confidence=low%'",
    ]
    params: list[object] = [profile.province]

    if profile.score is not None:
        conditions.append("score BETWEEN ? AND ?")
        params.extend([profile.score - max(SCORE_WINDOW, 35), profile.score + max(SCORE_WINDOW, 35)])
    elif profile.rank is not None:
        conditions.append("rank BETWEEN ? AND ?")
        params.extend([max(1, profile.rank - 50000), profile.rank + 50000])

    major_clause = _build_major_clause(profile.preferred_majors)
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    order_parts = [
        "year DESC",
        "CASE WHEN major = '院校专业组最低分' THEN 0 ELSE 1 END ASC",
    ]
    if profile.rank is not None:
        order_parts.append("ABS(rank - ?) ASC")
        params.append(profile.rank)
    if profile.score is not None:
        order_parts.append("ABS(score - ?) ASC")
        params.append(profile.score)

    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY {", ".join(order_parts)}
        LIMIT ?
    """
    params.append(max(80, limit))
    return conn.execute(sql, params).fetchall()


def _load_national_reference_records(profile: StudentProfile, limit: int) -> List[AdmissionRecord]:
    db_path = find_real_db_path()
    if not db_path:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _query_national_reference_rows(conn, profile, limit)
    finally:
        conn.close()

    records: List[AdmissionRecord] = []
    for row in rows:
        if not _is_valid_row(row) or not _row_matches_subject(row, profile):
            continue
        record = _row_to_record(row)
        if profile.province and profile.province in record.province:
            continue
        source_province = record.province or "外省"
        record.province = profile.province
        record.min_rank = 0
        record.source = f"{record.source}；原始生源省份：{source_province}；非{profile.province}生源省份参考"
        records.append(record)
    return records


def _query_national_reference_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    limit: int,
) -> List[sqlite3.Row]:
    major_clause = _build_major_clause(profile.preferred_majors)
    rows: list[sqlite3.Row] = []
    if profile.score is None and profile.rank is not None:
        rows.extend(_query_national_rank_reference_rows(conn, profile, limit // 2, major_clause))
    if profile.score is not None:
        rows.extend(_query_national_score_reference_rows(conn, profile, limit, major_clause))
    return rows


def _query_national_rank_reference_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    limit: int,
    major_clause: tuple[str, list[str]] | None,
) -> List[sqlite3.Row]:
    conditions = [
        "province NOT LIKE ?",
        "rank IS NOT NULL",
        "rank > 0",
        "rank BETWEEN ? AND ?",
        "score IS NOT NULL",
        "score > 0",
    ]
    params: list[object] = [f"%{profile.province}%", max(1, profile.rank - 30000), profile.rank + 30000]
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY year DESC, ABS(rank - ?) ASC
        LIMIT ?
    """
    params.extend([profile.rank, max(80, limit)])
    return conn.execute(sql, params).fetchall()


def _query_national_score_reference_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    limit: int,
    major_clause: tuple[str, list[str]] | None,
) -> List[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    per_band_limit = max(60, limit // 6)
    for low_delta, high_delta in ((6, SCORE_WINDOW), (-5, 5), (-SCORE_WINDOW, -6)):
        low, high = sorted((profile.score + low_delta, profile.score + high_delta))
        conditions = [
            "province NOT LIKE ?",
            "score IS NOT NULL",
            "score > 0",
            "score BETWEEN ? AND ?",
        ]
        params: list[object] = [f"%{profile.province}%", low, high]
        if major_clause:
            conditions.append(major_clause[0])
            params.extend(major_clause[1])

        sql = f"""
            SELECT province, year, school, major, score, rank, source
            FROM admission
            WHERE {" AND ".join(conditions)}
            ORDER BY year DESC,
                CASE WHEN rank IS NOT NULL AND rank > 0 THEN 0 ELSE 1 END ASC,
                ABS(score - ?) ASC
            LIMIT ?
        """
        params.extend([profile.score, per_band_limit])
        rows.extend(conn.execute(sql, params).fetchall())
    return rows


def _load_city_reference_records(profile: StudentProfile, limit: int) -> List[AdmissionRecord]:
    db_path = find_real_db_path()
    if not db_path:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _query_city_reference_rows(conn, profile, limit * 4)
    finally:
        conn.close()
    return [_row_to_record(row) for row in rows if _is_valid_row(row) and _row_matches_subject(row, profile)]


def _query_city_reference_rows(conn: sqlite3.Connection, profile: StudentProfile, limit: int) -> List[sqlite3.Row]:
    conditions = ["province LIKE ?", "score IS NOT NULL", "score > 0"]
    params: list[object] = [f"%{profile.province}%"]

    major_clause = _build_major_clause(profile.preferred_majors)
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    order_expr = "ABS(score - ?)" if profile.score is not None else "year DESC"
    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY year DESC, {order_expr} ASC
        LIMIT ?
    """
    if profile.score is not None:
        params.append(profile.score)
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def _build_registry_city_reference_records(profile: StudentProfile) -> List[AdmissionRecord]:
    db_path = find_real_db_path()
    if not db_path:
        return []

    school_names = [
        school
        for school, city in _load_school_city_registry().items()
        if city in profile.preferred_regions
    ]
    if not school_names:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _query_school_reference_rows(conn, school_names, profile, limit=max(80, len(school_names) * 8))
    finally:
        conn.close()

    records: List[AdmissionRecord] = []
    for row in rows:
        if not _is_valid_row(row) or not _row_matches_subject(row, profile):
            continue
        record = _row_to_record(row)
        if record.city not in profile.preferred_regions:
            continue
        if profile.province and profile.province not in record.province:
            source_province = record.province or "外省"
            record.province = profile.province
            record.min_rank = 0
            record.source = f"{record.source}；原始生源省份：{source_province}；非{profile.province}生源省份参考"
        records.append(record)

    if len(records) >= len(profile.preferred_regions) * 4:
        return records

    existing_schools = {item.school_name for item in records}
    for school_name in school_names:
        city = _lookup_school_city(school_name)
        if school_name in existing_schools or city not in profile.preferred_regions:
            continue
        records.append(
            AdmissionRecord(
                year=0,
                province=profile.province,
                subject_type=profile.subject_type,
                school_name=school_name,
                major_name="暂无本地录取线",
                city=city,
                min_score=0,
                min_rank=0,
                school_level=_infer_school_level(school_name),
                tags=_infer_tags(school_name, ""),
                source="school_city_registry.json；暂无本地分数线，仅作城市学校参考",
            )
        )
    return records


def _query_school_reference_rows(
    conn: sqlite3.Connection,
    school_names: List[str],
    profile: StudentProfile,
    limit: int,
) -> List[sqlite3.Row]:
    rows: List[sqlite3.Row] = []
    score = profile.score or 0
    for school_name in school_names:
        sql = """
            SELECT province, year, school, major, score, rank, source
            FROM admission
            WHERE school = ?
              AND ((score IS NOT NULL AND score > 0) OR (rank IS NOT NULL AND rank > 0))
            ORDER BY
              CASE WHEN province LIKE ? THEN 0 ELSE 1 END,
              year DESC,
              CASE WHEN ? > 0 AND score IS NOT NULL THEN ABS(score - ?) ELSE 999999 END ASC
            LIMIT 6
        """
        rows.extend(conn.execute(sql, (school_name, f"%{profile.province}%", score, score)).fetchall())
        if len(rows) >= limit:
            break
    return rows


def _query_rows(conn: sqlite3.Connection, profile: StudentProfile, limit: int) -> List[sqlite3.Row]:
    if profile.score is not None:
        return _query_score_tier_rows(conn, profile, limit)

    conditions = ["province LIKE ?", "score IS NOT NULL", "score > 0"]
    params: list[object] = [f"%{profile.province}%"]
    use_rank_window = profile.rank is not None and profile.score is None

    if use_rank_window:
        conditions.extend(["rank IS NOT NULL", "rank > 0"])
        low = max(1, profile.rank - 30000)
        high = profile.rank + 45000
        conditions.append("rank BETWEEN ? AND ?")
        params.extend([low, high])
    major_clause = _build_major_clause(profile.preferred_majors)
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY year DESC,
            CASE WHEN ? > 0 THEN ABS(rank - ?) ELSE 0 END ASC,
            CASE WHEN ? > 0 THEN ABS(score - ?) ELSE 0 END ASC
        LIMIT ?
    """
    rank_for_order = profile.rank if use_rank_window else 0
    score_for_order = profile.score or 0
    params.extend([rank_for_order, rank_for_order, score_for_order, score_for_order, limit])
    rows = conn.execute(sql, params).fetchall()

    if rows:
        return rows

    if profile.score is not None:
        score_rows = _query_score_window_rows(conn, profile, limit, major_clause)
        if score_rows:
            return score_rows

    return rows


def _query_score_tier_rows(conn: sqlite3.Connection, profile: StudentProfile, limit: int) -> List[sqlite3.Row]:
    major_clause = _build_major_clause(profile.preferred_majors)
    rows: list[sqlite3.Row] = []
    per_band_limit = max(80, limit // 3)
    for low_delta, high_delta in ((6, SCORE_WINDOW), (-5, 5), (-SCORE_WINDOW, -6)):
        rows.extend(
            _query_score_band_rows(
                conn,
                profile,
                profile.score + low_delta,
                profile.score + high_delta,
                per_band_limit,
                major_clause,
            )
        )
    if rows:
        return rows
    return _query_score_window_rows(conn, profile, limit, major_clause)


def _query_score_band_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    low_score: int,
    high_score: int,
    limit: int,
    major_clause: tuple[str, list[str]] | None,
) -> List[sqlite3.Row]:
    low, high = sorted((low_score, high_score))
    conditions = ["province LIKE ?", "score IS NOT NULL", "score > 0", "score BETWEEN ? AND ?"]
    params: list[object] = [f"%{profile.province}%", low, high]
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY year DESC,
            CASE WHEN rank IS NOT NULL AND rank > 0 THEN 0 ELSE 1 END ASC,
            ABS(score - ?) ASC
        LIMIT ?
    """
    params.extend([profile.score, limit])
    return conn.execute(sql, params).fetchall()


def _query_score_window_rows(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    limit: int,
    major_clause: tuple[str, list[str]] | None,
) -> List[sqlite3.Row]:
    conditions = ["province LIKE ?", "score IS NOT NULL", "score > 0", "score BETWEEN ? AND ?"]
    params: list[object] = [f"%{profile.province}%", profile.score - SCORE_WINDOW, profile.score + SCORE_WINDOW]
    if major_clause:
        conditions.append(major_clause[0])
        params.extend(major_clause[1])

    sql = f"""
        SELECT province, year, school, major, score, rank, source
        FROM admission
        WHERE {" AND ".join(conditions)}
        ORDER BY year DESC,
            CASE WHEN rank IS NOT NULL AND rank > 0 THEN 0 ELSE 1 END ASC,
            ABS(score - ?) ASC
        LIMIT ?
    """
    params.extend([profile.score, limit])
    rows = conn.execute(sql, params).fetchall()
    return rows


def _build_major_clause(majors: Iterable[str]) -> tuple[str, list[str]] | None:
    keywords = [item.strip() for item in majors if item.strip()]
    if not keywords:
        return None
    clauses = ["major LIKE ?" for _ in keywords]
    return "(" + " OR ".join(clauses) + ")", [f"%{item}%" for item in keywords]


def _is_valid_row(row: sqlite3.Row) -> bool:
    school = _clean_school(str(row["school"] or "").strip())
    major = str(row["major"] or "").strip()
    source = str(row["source"] or "").strip()
    if not school or len(school) > 40:
        return False
    if any(fragment in school for fragment in BAD_SCHOOL_FRAGMENTS):
        return False
    if not _looks_like_school_name(school):
        return False
    if source and any(fragment in source for fragment in NOISY_SOURCE_KEYWORDS):
        return False
    if source and "非" not in source and not any(fragment in source for fragment in VALID_SOURCE_KEYWORDS):
        return False
    if major and len(major) > 80:
        return False
    return True


def _row_matches_subject(row: sqlite3.Row, profile: StudentProfile) -> bool:
    subject = profile.subject_type
    if not subject:
        return True
    text = f"{row['source'] or ''} {row['major'] or ''}"
    if "third_party:baidunetdisk_2026_gaokao_pack" in text:
        if subject == "物理类":
            return "subject=物理类" in text or "subject=理科" in text or "subject=综合" in text
        if subject == "历史类":
            return "subject=历史类" in text or "subject=文科" in text or "subject=综合" in text
        if subject in {"综合", "普通类"}:
            return "subject=综合" in text or "subject=普通类" in text
    if subject == "物理类":
        return "历史组" not in text and "历史类" not in text and "首选历史" not in text and "文科" not in text
    if subject == "历史类":
        return "物理组" not in text and "物理类" not in text and "首选物理" not in text and "理科" not in text
    return True


def _looks_like_school_name(school: str) -> bool:
    cleaned = re.sub(r"第[0-9０-９一二三四五六七八九十]+组.*$", "", school).strip()
    return cleaned.endswith(("大学", "学院", "学校"))


def _clean_school(raw: str) -> str:
    value = re.sub(r"\s+", "", raw.strip())
    value = re.sub(r"(湖北省教育厅招生办公室|招生办公室).*$", "", value)
    return value[:40]


def _clean_rank(score: int, rank: int) -> int:
    if score >= 500 and 0 < rank < 1000:
        return 0
    return rank


def _row_to_record(row: sqlite3.Row) -> AdmissionRecord:
    school = _clean_school(str(row["school"] or "").strip())
    major = _clean_major(str(row["major"] or "").strip())
    source = str(row["source"] or "").strip()
    score = int(row["score"] or 0)
    rank = _clean_rank(score, int(row["rank"] or 0))
    return AdmissionRecord(
        year=int(row["year"] or 0),
        province=str(row["province"] or "").strip(),
        subject_type="",
        school_name=school,
        major_name=major or "未细分专业",
        city=_infer_city(school),
        min_score=score,
        min_rank=rank,
        school_level=_infer_school_level(school),
        tags=_infer_tags(school, major),
        source=source,
    )


def _clean_major(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"(办学地点|学费|校区)[，,：:].*$", "", value)
    value = value.rstrip("，,（(")
    if re.fullmatch(r"[A-Z]?\d{1,5}", value):
        return ""
    if value in {"不限", "物", "史", "化", "政", "生", "地", "理科", "文科", "综合"}:
        return ""
    return value[:60]


def _dedup_records(records: List[AdmissionRecord]) -> List[AdmissionRecord]:
    seen: set[tuple[str, str, int, int, str]] = set()
    result: List[AdmissionRecord] = []
    for record in records:
        key = (record.school_name, record.major_name, record.min_score, record.min_rank, record.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _infer_school_level(school: str) -> str:
    if school in {"武汉大学", "华中科技大学"}:
        return "985 211 双一流"
    if school in {"武汉理工大学", "华中师范大学", "中南财经政法大学", "中国地质大学", "华中农业大学"}:
        return "211 双一流"
    if school in {"湖北大学", "武汉科技大学", "三峡大学", "武汉工程大学", "长江大学"}:
        return "省重点"
    return ""


def _infer_city(school: str) -> str:
    registry_city = _lookup_school_city(school)
    if registry_city:
        return registry_city

    city_map = {
        "北京": [
            "北京",
            "清华大学",
            "中国人民大学",
            "中国农业大学",
            "中央民族大学",
            "中央财经大学",
            "中国政法大学",
            "中国传媒大学",
            "对外经济贸易大学",
            "华北电力大学",
            "中国矿业大学",
            "中国地质大学",
            "中国石油大学",
            "外交学院",
            "国际关系学院",
            "首都",
        ],
        "上海": [
            "上海",
            "复旦大学",
            "同济大学",
            "华东师范大学",
            "上海交通大学",
            "上海财经大学",
            "上海大学",
            "华东理工大学",
            "东华大学",
            "上海外国语大学",
            "上海科技大学",
            "上海中医药大学",
            "上海理工大学",
            "上海师范大学",
            "上海海事大学",
            "上海电力大学",
            "上海政法学院",
        ],
        "南京": ["南京", "东南大学", "河海大学", "中国药科大学", "南京理工大学", "南京航空航天大学"],
        "苏州": ["苏州大学", "西交利物浦大学"],
        "杭州": ["浙江大学", "杭州", "中国美术学院"],
        "宁波": ["宁波", "宁波诺丁汉大学"],
        "温州": ["温州"],
        "广州": ["广州", "中山大学", "华南理工大学", "暨南大学", "南方医科大学"],
        "深圳": ["深圳", "南方科技大学", "香港中文大学（深圳）"],
        "天津": ["天津", "南开大学"],
        "重庆": ["重庆", "西南大学"],
        "成都": ["成都", "四川大学", "电子科技大学", "西南财经大学", "西南交通大学"],
        "西安": ["西安", "西北工业大学", "西安交通大学", "西安电子科技大学", "长安大学"],
        "哈尔滨": ["哈尔滨", "哈尔滨工业大学", "哈尔滨工程大学", "哈尔滨医科大学"],
        "长春": ["吉林大学", "东北师范大学", "长春"],
        "兰州": ["兰州大学", "兰州"],
        "厦门": ["厦门大学", "厦门"],
        "长沙": ["湖南大学", "中南大学", "湖南师范大学", "长沙"],
        "青岛": ["中国海洋大学", "青岛"],
        "武汉": ["武汉", "湖北大学", "华中", "中南财经政法", "中国地质大学"],
        "宜昌": ["三峡大学"],
        "荆州": ["长江大学"],
    }
    for city, tokens in city_map.items():
        if any(token in school for token in tokens):
            return city
    return ""


@lru_cache(maxsize=1)
def _load_school_city_registry() -> dict[str, str]:
    if not SCHOOL_CITY_REGISTRY_FILE.exists():
        return {}
    try:
        raw = json.loads(SCHOOL_CITY_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    registry: dict[str, str] = {}
    for school, item in raw.items():
        if isinstance(item, dict):
            city = str(item.get("city", "")).strip()
        else:
            city = str(item).strip()
        school_name = str(school).strip()
        if school_name and city:
            registry[school_name] = city
    return registry


def _lookup_school_city(school: str) -> str:
    registry = _load_school_city_registry()
    if school in registry:
        return registry[school]
    for known_school, city in registry.items():
        if known_school and known_school in school:
            return city
    return ""


def _school_city_registry_items() -> dict[str, str]:
    return _load_school_city_registry()


def _infer_tags(school: str, major: str) -> List[str]:
    text = f"{school}{major}"
    tags: List[str] = []
    mapping = {
        "计算机": ["计算机", "就业", "高薪"],
        "软件": ["计算机", "就业", "高薪"],
        "人工智能": ["计算机", "AI", "高薪"],
        "电子": ["电子信息", "工科", "就业"],
        "通信": ["电子信息", "工科", "就业"],
        "电气": ["电网", "工科", "稳定"],
        "自动化": ["工科", "国企", "就业"],
        "法学": ["法学", "考公"],
        "汉语言": ["汉语言", "考公", "师范"],
        "师范": ["师范", "考编", "稳定"],
        "医学": ["医学", "稳定"],
        "临床": ["医学", "稳定"],
        "口腔": ["医学", "高薪"],
        "会计": ["财会", "考公"],
        "财务": ["财会", "考公"],
    }
    for token, values in mapping.items():
        if token in text:
            for value in values:
                if value not in tags:
                    tags.append(value)
    return tags
