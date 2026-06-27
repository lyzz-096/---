from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StudentProfile:
    province: str
    subject_type: str
    score: Optional[int] = None
    rank: Optional[int] = None
    rank_source: str = "manual"
    preferred_majors: List[str] = field(default_factory=list)
    excluded_majors: List[str] = field(default_factory=list)
    preferred_regions: List[str] = field(default_factory=list)
    career_goal: str = ""
    family_background: str = ""
    accept_postgraduate: bool = False
    parent_expectation: str = ""
    student_expectation: str = ""
    city_priority: str = ""
    school_priority: str = ""
    major_priority: str = ""
    stability_priority: str = ""
    salary_priority: str = ""
    postgraduate_priority: str = ""
    normalized_notes: List[str] = field(default_factory=list)


@dataclass
class AdmissionRecord:
    year: int
    province: str
    subject_type: str
    school_name: str
    major_name: str
    city: str
    min_score: int
    min_rank: int
    school_level: str
    tags: List[str]
    city_tier: str = ""
    major_heat: str = ""
    employment_score: int = 60
    postgraduate_score: int = 60
    stability_score: int = 60
    salary_score: int = 60
    plan_change: int = 0
    source: str = ""


@dataclass
class ScoreRankRecord:
    year: int
    province: str
    subject_type: str
    score: int
    rank: int
    source: str = ""
    source_type: str = ""
    url: str = ""


@dataclass
class Recommendation:
    school_name: str
    major_name: str
    city: str
    year: int
    min_score: int
    min_rank: int
    tier: str
    fit_score: float
    reason: str
    risk: str
    score_breakdown: List[str] = field(default_factory=list)
