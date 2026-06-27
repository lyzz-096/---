from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import List
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .models import StudentProfile


SOURCE_REGISTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "source_registry.json"
QUERY_WORKERS = 4
SEARCH_WORKERS = 8
PAGE_WORKERS = 10
SEARCH_TIMEOUT_SECONDS = 4
PAGE_TIMEOUT_SECONDS = 3
SEARCH_MAX_BYTES = 120_000
PAGE_MAX_BYTES = 180_000


@dataclass
class ResearchQuery:
    purpose: str
    query: str
    preferred_sources: List[str]


@dataclass
class ResearchEvidence:
    purpose: str
    query: str
    title: str
    url: str
    source_type: str
    snippet: str
    numeric_clues: List[str]
    status: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            stripped = " ".join(data.split())
            if stripped:
                self.parts.append(stripped)

    def text(self) -> str:
        return " ".join(self.parts)


PROVINCE_RANK_SEEDS = {
    "湖北": [
        {
            "title": "湖北省2025年普通高考总分一分一段统计表-普通类",
            "url": "https://www.hbea.edu.cn/html/2025-06/15292.html",
            "snippet": "湖北省教育考试院发布的普通高考总分一分一段统计表入口，含首选物理、首选历史。",
        }
    ]
}


def load_source_registry() -> dict[str, list[dict[str, object]]]:
    if not SOURCE_REGISTRY_FILE.exists():
        return {}
    try:
        raw = json.loads(SOURCE_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(key): list(value) for key, value in raw.items() if isinstance(value, list)}


SCHOOL_ADMISSION_SEEDS = {
    "武汉理工大学": [
        {
            "title": "武汉理工大学本科招生网",
            "url": "https://zs.whut.edu.cn/",
            "snippet": "武汉理工大学本科招生网，含招生计划、历年分数、录取查询等栏目。",
        }
    ],
    "华中农业大学": [
        {
            "title": "华中农业大学本科招生网",
            "url": "https://bkzs.hzau.edu.cn/",
            "snippet": "华中农业大学本科招生网。",
        }
    ],
    "湖北大学": [
        {
            "title": "湖北大学本科招生信息网",
            "url": "https://zs.hubu.edu.cn/",
            "snippet": "湖北大学本科招生信息网。",
        }
    ],
    "武汉科技大学": [
        {
            "title": "武汉科技大学招生就业",
            "url": "https://www.wust.edu.cn/zsjy.htm",
            "snippet": "武汉科技大学招生就业入口，含本科招生相关链接。",
        }
    ],
    "三峡大学": [
        {
            "title": "三峡大学本科招生信息网",
            "url": "https://zs.ctgu.edu.cn/",
            "snippet": "三峡大学本科招生信息网。",
        }
    ],
    "武汉工程大学": [
        {
            "title": "武汉工程大学本科招生网",
            "url": "https://zsb.wit.edu.cn/",
            "snippet": "武汉工程大学本科招生网。",
        }
    ],
}


def build_research_queries(profile: StudentProfile, candidate_schools: List[str] | None = None) -> List[ResearchQuery]:
    schools = candidate_schools or []
    majors = profile.preferred_majors or ["目标专业"]
    year = "2026"

    queries = [
        ResearchQuery(
            purpose="分数转位次",
            query=f"{profile.province} {year} 一分一段表 {profile.subject_type} {profile.score or ''}".strip(),
            preferred_sources=["省教育考试院", "省考试院"],
        )
    ]

    for major in majors[:3]:
        queries.append(
            ResearchQuery(
                purpose="专业方向候选院校",
                query=f"{profile.province} {profile.subject_type} {major} 录取位次 招生计划",
                preferred_sources=["省教育考试院", "高校本科招生网", "阳光高考"],
            )
        )

    for school in schools[:5]:
        for major in majors[:2]:
            queries.extend(
                [
                    ResearchQuery(
                        purpose="高校专业录取数据",
                        query=f"{school} 本科招生网 {profile.province} {major} 录取分数 位次",
                        preferred_sources=["高校本科招生网"],
                    ),
                    ResearchQuery(
                        purpose="高校招生计划变化",
                        query=f"{school} {year} {profile.province} 招生计划 {major}",
                        preferred_sources=["高校本科招生网", "阳光高考"],
                    ),
                ]
            )

    return queries


def execute_research(
    profile: StudentProfile,
    candidate_schools: List[str] | None = None,
    per_query_limit: int = 3,
    max_queries: int = 6,
) -> List[ResearchEvidence]:
    queries = build_research_queries(profile, candidate_schools)[:max_queries]
    if not queries:
        return []

    evidence_by_index: dict[int, List[ResearchEvidence]] = {}
    worker_count = min(QUERY_WORKERS, len(queries))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(_execute_research_query, item, profile, per_query_limit): index
            for index, item in enumerate(queries)
        }
        for future in as_completed(future_map):
            evidence_by_index[future_map[future]] = future.result()

    evidence: List[ResearchEvidence] = []
    seen_evidence_urls: set[str] = set()
    for index in range(len(queries)):
        for item in evidence_by_index.get(index, []):
            dedup_key = item.url or f"{item.purpose}:{item.title}"
            if dedup_key in seen_evidence_urls:
                continue
            seen_evidence_urls.add(dedup_key)
            evidence.append(item)
    return evidence


def _execute_research_query(
    item: ResearchQuery,
    profile: StudentProfile,
    per_query_limit: int,
) -> List[ResearchEvidence]:
    seed_items = _seed_results(item, profile)
    registry_items = [result for result in seed_items if result.get("source") == "registry"]
    if len(registry_items) >= per_query_limit:
        raw_items = registry_items
    else:
        raw_items = seed_items + _search_many(item.query, per_query_limit * 3)
    search_items = _rank_search_results(raw_items, item, profile)[:per_query_limit]
    if not search_items:
        return [
            ResearchEvidence(
                purpose=item.purpose,
                query=item.query,
                title="未找到搜索结果",
                url="",
                source_type="missing",
                snippet="搜索接口没有返回结果，建议换关键词或手动指定来源。",
                numeric_clues=[],
                status="empty",
            )
        ]

    page_texts = _fetch_pages(search_items)
    evidence: List[ResearchEvidence] = []
    for result in search_items:
        page_text = page_texts.get(result["url"], "")
        combined_text = f"{result['title']} {result['snippet']} {page_text}"
        evidence.append(
            ResearchEvidence(
                purpose=item.purpose,
                query=item.query,
                title=result["title"],
                url=result["url"],
                source_type=_classify_source(result["url"], result["title"]),
                snippet=_shorten(result["snippet"] or page_text, 220),
                numeric_clues=_extract_numeric_clues(combined_text),
                status="ok" if page_text else "search_only",
            )
        )
    return evidence


def _seed_results(item: ResearchQuery, profile: StudentProfile) -> List[dict[str, str]]:
    seeded = _registry_seed_results(item, profile)
    if item.purpose == "分数转位次":
        seeded.extend(PROVINCE_RANK_SEEDS.get(profile.province, []))
        return _dedup_seed_results(seeded)

    for school_name, pages in SCHOOL_ADMISSION_SEEDS.items():
        if school_name in item.query:
            seeded.extend(pages)
    return _dedup_seed_results(seeded)


def _registry_seed_results(item: ResearchQuery, profile: StudentProfile) -> List[dict[str, str]]:
    province_sources = load_source_registry().get(profile.province, [])
    results: List[dict[str, str]] = []
    for source in province_sources:
        purposes = source.get("purpose", [])
        if isinstance(purposes, str):
            purposes = [purposes]
        hints = source.get("query_hints", [])
        if isinstance(hints, str):
            hints = [hints]

        source_purpose_match = item.purpose in purposes
        hint_match = any(str(hint) and str(hint) in item.query for hint in hints)
        if not source_purpose_match and not hint_match:
            continue

        title = str(source.get("title", "")).strip()
        url = str(source.get("url", "")).strip()
        snippet = str(source.get("snippet", "")).strip()
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet, "source": "registry"})
    return results


def _dedup_seed_results(items: List[dict[str, str]]) -> List[dict[str, str]]:
    result: List[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(item)
    return result


def render_research_evidence(evidence: List[ResearchEvidence]) -> str:
    lines = ["联网取证结果："]
    if not evidence:
        lines.append("暂无结果。")
        return "\n".join(lines)

    for item in evidence:
        source_label = _source_label(item.source_type)
        clues = "；".join(item.numeric_clues[:4]) if item.numeric_clues else "暂未抽到明确数字线索"
        lines.append(f"- [{source_label}] {item.purpose}：{item.title}")
        if item.url:
            lines.append(f"  链接：{item.url}")
        lines.append(f"  摘要：{item.snippet}")
        lines.append(f"  数字线索：{clues}")
    lines.append("")
    lines.append("提示：联网抽取结果只是第一轮取证，正式填报前仍要打开官方原文核对年份、专业组、批次和招生计划口径。")
    return "\n".join(lines)


def render_research_plan(profile: StudentProfile, candidate_schools: List[str] | None = None) -> str:
    lines = ["联网取证计划："]
    for item in build_research_queries(profile, candidate_schools):
        sources = "、".join(item.preferred_sources)
        lines.append(f"- {item.purpose}：{item.query}（优先来源：{sources}）")
    return "\n".join(lines)


def _search_bing_rss(query: str, limit: int) -> List[dict[str, str]]:
    url = f"https://www.bing.com/search?format=rss&mkt=zh-CN&cc=CN&q={quote_plus(query)}"
    try:
        payload = _http_get(url, timeout=SEARCH_TIMEOUT_SECONDS, max_bytes=SEARCH_MAX_BYTES)
        root = ET.fromstring(payload)
    except Exception:
        return []

    results: List[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = _clean_xml_text(item.findtext("title"))
        link = _clean_xml_text(item.findtext("link"))
        description = _clean_xml_text(item.findtext("description"))
        if title and link:
            results.append({"title": title, "url": link, "snippet": description})
        if len(results) >= limit:
            break
    return results


@lru_cache(maxsize=256)
def _search_bing_rss_cached(query: str, limit: int) -> tuple[tuple[str, str, str], ...]:
    return tuple((item["title"], item["url"], item["snippet"]) for item in _search_bing_rss(query, limit))


def _search_many(query: str, limit: int) -> List[dict[str, str]]:
    variants = [
        query,
        f"{query} site:edu.cn",
        f"{query} 招生网",
        f"{query} 教育考试院",
        f"{query} 阳光高考",
    ]
    merged: List[dict[str, str]] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(variants))) as executor:
        future_map = {executor.submit(_search_bing_rss_cached, variant, limit): variant for variant in variants}
        for future in as_completed(future_map):
            for title, url, snippet in future.result():
                if url in seen:
                    continue
                seen.add(url)
                merged.append({"title": title, "url": url, "snippet": snippet})
    return merged


def _rank_search_results(results: List[dict[str, str]], query: ResearchQuery, profile: StudentProfile) -> List[dict[str, str]]:
    scored: List[tuple[int, dict[str, str]]] = []
    query_terms = [term for term in re.split(r"\s+", query.query) if term]
    required_context = [profile.province, profile.subject_type, "高考", "招生", "录取", "位次", "一分一段"]
    for result in results:
        text = f"{result['title']} {result['snippet']} {result['url']}"
        is_registry_source = result.get("source") == "registry"
        if not is_registry_source and _looks_irrelevant(text, profile, query, query_terms, required_context):
            continue
        score = 0
        source_type = _classify_source(result["url"], result["title"])
        score += {"exam_official": 40, "university": 32, "sunshine": 28, "third_party": 8}.get(source_type, 0)
        if is_registry_source:
            score += 50
        score += sum(6 for term in query_terms if term and term in text)
        score += sum(4 for term in required_context if term and term in text)
        scored.append((score, result))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored]


def _looks_irrelevant(
    text: str,
    profile: StudentProfile,
    query: ResearchQuery,
    query_terms: List[str],
    required_context: List[str],
) -> bool:
    lowered = text.lower()
    obvious_noise = ["yahoo", "specialchar", "unicode", "百科", "地图", "天气", "旅游", "人民政府门户网站"]
    if any(token in lowered for token in obvious_noise):
        return True

    if query.purpose == "分数转位次":
        return not any(term in text for term in ["一分一段", "位次", "排位"]) or "高考" not in text

    if query.purpose == "专业方向候选院校":
        major_terms = [term for term in profile.preferred_majors if term]
        has_major = any(term in text for term in major_terms)
        has_admission_signal = any(term in text for term in ["招生", "录取", "位次", "投档", "专业组"])
        return not (profile.province in text and has_major and has_admission_signal)

    if query.purpose.startswith("高校"):
        school_names = [term for term in query_terms if term.endswith("大学") or term.endswith("学院")]
        has_school = any(term in text for term in school_names)
        has_admission_signal = any(term in text for term in ["本科招生", "招生网", "招生计划", "历年分数", "录取"])
        return not (has_school and has_admission_signal)

    meaningful_hits = sum(1 for term in query_terms + required_context if term and term in text)
    if profile.province not in text and meaningful_hits < 3:
        return True
    return meaningful_hits < 2


def _fetch_page_text(url: str) -> str:
    try:
        html = _http_get(url, timeout=PAGE_TIMEOUT_SECONDS, max_bytes=PAGE_MAX_BYTES)
    except Exception:
        return ""

    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return _shorten(parser.text(), 4000)


@lru_cache(maxsize=512)
def _fetch_page_text_cached(url: str) -> str:
    return _fetch_page_text(url)


def _fetch_pages(search_items: List[dict[str, str]]) -> dict[str, str]:
    urls = [
        item["url"]
        for item in search_items
        if item.get("url") and not _should_skip_page_fetch(item)
    ]
    if not urls:
        return {}

    page_texts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(PAGE_WORKERS, len(urls))) as executor:
        future_map = {executor.submit(_fetch_page_text_cached, url): url for url in urls}
        for future in as_completed(future_map):
            page_texts[future_map[future]] = future.result()
    return page_texts


def _should_skip_page_fetch(item: dict[str, str]) -> bool:
    url = item.get("url", "").lower()
    if url.endswith((".xls", ".xlsx", ".pdf", ".doc", ".docx")):
        return True
    if "download" in url or "downfile" in url:
        return True
    return item.get("source") == "registry" and bool(item.get("snippet"))


def _http_get(url: str, timeout: int, max_bytes: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GaokaoAdvisor/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes)
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _classify_source(url: str, title: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    text = f"{host} {url.lower()} {title}"
    if "gaokao.chsi.com.cn" in host or "阳光高考" in title:
        return "sunshine"
    if any(token in text for token in ["考试院", "教育考试院", "招生考试院", "jyt.", "zsks", "eea", "hbea", "zjzs.net"]):
        return "exam_official"
    if host.endswith(".edu.cn") or any(token in text for token in ["本科招生网", "招生网", "admission", "zsb", "bkzs"]):
        return "university"
    return "third_party"


def _extract_numeric_clues(text: str) -> List[str]:
    normalized = " ".join(text.split())
    patterns = [
        r"[^。；;，,\n]{0,18}\d{2,4}\s*分[^。；;，,\n]{0,18}",
        r"[^。；;，,\n]{0,18}(?:位次|排名|排位)[^。；;，,\n]{0,18}\d{3,8}[^。；;，,\n]{0,18}",
        r"[^。；;，,\n]{0,18}\d{3,8}\s*(?:名|位)[^。；;，,\n]{0,18}",
        r"[^。；;，,\n]{0,18}(?:招生计划|计划招生|招生人数)[^。；;，,\n]{0,18}\d{1,5}[^。；;，,\n]{0,18}",
        r"[^。；;，,\n]{0,18}\d{4}\s*年[^。；;，,\n]{0,24}",
    ]
    clues: List[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, normalized):
            clue = _shorten(match.strip(), 90)
            if clue and clue not in clues:
                clues.append(clue)
            if len(clues) >= 8:
                return clues
    return clues


def _source_label(source_type: str) -> str:
    return {
        "exam_official": "省考试院/教育官方",
        "university": "高校招生网",
        "sunshine": "阳光高考",
        "third_party": "第三方待复核",
        "missing": "未命中",
    }.get(source_type, source_type)


def _clean_xml_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _shorten(value: str, max_length: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1] + "…"
