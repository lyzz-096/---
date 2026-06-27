from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "admission_clean.db"
SOURCE_REGISTRY = Path(__file__).resolve().parent.parent / "data" / "source_registry.json"
SCORE_RANK_OVERRIDES = Path(__file__).resolve().parent.parent / "data" / "score_rank_overrides.json"
PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]


def load_json(path: Path) -> object:
    if not path.exists():
        return {} if path.name.endswith("registry.json") else []
    return json.loads(path.read_text(encoding="utf-8"))


def audit_db(db_path: Path) -> dict[str, dict[str, int]]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT province, MAX(year) AS latest_year,
                   SUM(CASE WHEN year=2025 THEN 1 ELSE 0 END) AS records_2025,
                   SUM(CASE WHEN year=2025 AND rank > 0 THEN 1 ELSE 0 END) AS rank_2025,
                   SUM(CASE WHEN rank > 0 THEN 1 ELSE 0 END) AS rank_all,
                   COUNT(*) AS total
            FROM admission
            GROUP BY province
            """
        ).fetchall()
    finally:
        conn.close()

    return {
        row[0]: {
            "latest_year": row[1] or 0,
            "records_2025": row[2] or 0,
            "rank_2025": row[3] or 0,
            "rank_all": row[4] or 0,
            "total": row[5] or 0,
        }
        for row in rows
    }


def province_status(metrics: dict[str, int], has_source: bool, has_official_rank: bool, has_third_party_rank: bool) -> str:
    if metrics.get("records_2025", 0) >= 1000 and has_official_rank:
        return "官方位次可用" if metrics.get("rank_2025", 0) == 0 else "浙江级"
    if metrics.get("records_2025", 0) >= 1000 and metrics.get("rank_2025", 0) >= 500:
        return "浙江级"
    if metrics.get("records_2025", 0) >= 1000:
        return "缺2025位次"
    if metrics.get("latest_year", 0) >= 2024 and has_source:
        return "可联网补强"
    if has_third_party_rank:
        return "临时位次"
    if has_source:
        return "有官网入口"
    return "待找来源"


def main() -> None:
    parser = argparse.ArgumentParser(description="查看各省 2025 高考资源库完善进度")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="admission_clean.db 路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    metrics = audit_db(Path(args.db))
    registry = load_json(SOURCE_REGISTRY)
    overrides = load_json(SCORE_RANK_OVERRIDES)
    official_rank_provinces = {
        item.get("province")
        for item in overrides
        if isinstance(item, dict) and item.get("source_type") == "exam_official"
    }
    third_party_rank_provinces = {
        item.get("province")
        for item in overrides
        if isinstance(item, dict) and item.get("source_type") == "third_party"
    }

    rows = []
    for province in PROVINCES:
        province_metrics = metrics.get(province, {})
        has_source = province in registry
        has_official_rank = province in official_rank_provinces
        has_third_party_rank = province in third_party_rank_provinces
        rows.append(
            {
                "province": province,
                "status": province_status(province_metrics, has_source, has_official_rank, has_third_party_rank),
                "latest_year": province_metrics.get("latest_year", 0),
                "records_2025": province_metrics.get("records_2025", 0),
                "rank_2025": province_metrics.get("rank_2025", 0),
                "official_sources": len(registry.get(province, [])) if isinstance(registry, dict) else 0,
                "has_rank_override": has_official_rank or has_third_party_rank,
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print("省份       状态       最新年  2025记录  2025位次  官方源  临时位次")
    for row in rows:
        override = "是" if row["has_rank_override"] else "否"
        print(
            f"{row['province']:8s} {row['status']:10s} {row['latest_year']:5d}"
            f" {row['records_2025']:9,d} {row['rank_2025']:9,d}"
            f" {row['official_sources']:6d} {override:>4s}"
        )


if __name__ == "__main__":
    main()
