from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from gaokao_tool.models import StudentProfile  # noqa: E402
from gaokao_tool.real_admission import find_real_db_path, load_real_admission_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Query bundled gaokao admission database.")
    parser.add_argument("--province", required=True, help="考生省份，例如 浙江、四川、湖北")
    parser.add_argument("--subject", required=True, help="选科/科类，例如 物理、历史、物化技、理科")
    parser.add_argument("--score", type=int, default=None, help="高考分数")
    parser.add_argument("--rank", type=int, default=None, help="高考位次")
    parser.add_argument("--major", action="append", default=[], help="偏好专业关键词，可重复")
    parser.add_argument("--exclude-major", action="append", default=[], help="排斥专业关键词，可重复")
    parser.add_argument("--region", action="append", default=[], help="偏好地区/城市，可重复")
    parser.add_argument("--goal", default="", help="升学、就业、考公等目标")
    parser.add_argument("--limit", type=int, default=30, help="返回记录数量")
    args = parser.parse_args()

    db_path = find_real_db_path()
    if not db_path:
        print(json.dumps(
            {
                "ok": False,
                "error": "missing_admission_clean_db",
                "expected": str(APP_ROOT / "data" / "admission_clean.db"),
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 2

    profile = StudentProfile(
        province=args.province,
        subject_type=args.subject,
        score=args.score,
        rank=args.rank,
        preferred_majors=args.major,
        excluded_majors=args.exclude_major,
        preferred_regions=args.region,
        career_goal=args.goal,
    )
    records = load_real_admission_records(profile, limit=args.limit)
    payload = {
        "ok": True,
        "db_path": str(db_path),
        "query": {
            "province": args.province,
            "subject": args.subject,
            "score": args.score,
            "rank": args.rank,
            "major": args.major,
            "region": args.region,
            "goal": args.goal,
        },
        "count": len(records),
        "records": [
            {
                "year": item.year,
                "province": item.province,
                "subject_type": item.subject_type,
                "school_name": item.school_name,
                "major_name": item.major_name,
                "city": item.city,
                "min_score": item.min_score,
                "min_rank": item.min_rank,
                "school_level": item.school_level,
                "tags": item.tags,
                "source": item.source,
            }
            for item in records
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
