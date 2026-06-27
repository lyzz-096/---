from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import AdmissionRecord, ScoreRankRecord, StudentProfile
from .real_admission import has_real_admission_db, load_real_admission_records


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_admissions.json"
SCORE_RANK_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_score_ranks.json"
SCORE_RANK_OVERRIDE_FILE = Path(__file__).resolve().parent.parent / "data" / "score_rank_overrides.json"


def load_admission_records(profile: StudentProfile | None = None) -> List[AdmissionRecord]:
    if profile is not None:
        real_records = load_real_admission_records(profile)
        if real_records or has_real_admission_db():
            return real_records

    raw_items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [
        AdmissionRecord(
            year=item["year"],
            province=item["province"],
            subject_type=item["subject_type"],
            school_name=item["school_name"],
            major_name=item["major_name"],
            city=item["city"],
            min_score=item["min_score"],
            min_rank=item["min_rank"],
            school_level=item["school_level"],
            tags=item["tags"],
            city_tier=item.get("city_tier", ""),
            major_heat=item.get("major_heat", ""),
            employment_score=item.get("employment_score", 60),
            postgraduate_score=item.get("postgraduate_score", 60),
            stability_score=item.get("stability_score", 60),
            salary_score=item.get("salary_score", 60),
            plan_change=item.get("plan_change", 0),
            source=item.get("source", "sample_admissions.json"),
        )
        for item in raw_items
    ]


def load_score_rank_records() -> List[ScoreRankRecord]:
    raw_items = json.loads(SCORE_RANK_FILE.read_text(encoding="utf-8"))
    if SCORE_RANK_OVERRIDE_FILE.exists():
        raw_items.extend(json.loads(SCORE_RANK_OVERRIDE_FILE.read_text(encoding="utf-8")))
    return [
        ScoreRankRecord(
            year=item["year"],
            province=item["province"],
            subject_type=item["subject_type"],
            score=item["score"],
            rank=item["rank"],
            source=item.get("source", ""),
            source_type=item.get("source_type", ""),
            url=item.get("url", ""),
        )
        for item in raw_items
    ]
