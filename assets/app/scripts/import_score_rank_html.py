from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "score_rank_overrides.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GaokaoAdvisor/0.2"


class TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        payload = response.read()
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    return payload.decode("utf-8", errors="replace")


def first_int(value: object) -> int | None:
    matches = re.findall(r"\d[\d,]*", str(value))
    if not matches:
        return None
    return int(matches[0].replace(",", ""))


def extract_rows(html: str) -> list[tuple[int, int]]:
    parser = TableTextParser()
    parser.feed(html)
    rows: list[tuple[int, int]] = []
    for row in parser.rows:
        nums = [first_int(cell) for cell in row]
        nums = [num for num in nums if num is not None]
        if len(nums) < 2:
            continue
        score = nums[0]
        rank = nums[-1]
        if 100 <= score <= 750 and rank > 0:
            rows.append((score, rank))
    if rows:
        return sorted(set(rows), reverse=True)

    for line in re.sub(r"<[^>]+>", " ", html).splitlines():
        nums = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", line)]
        if len(nums) >= 2 and 100 <= nums[0] <= 750 and nums[-1] > 0:
            rows.append((nums[0], nums[-1]))
    return sorted(set(rows), reverse=True)


def load_existing() -> list[dict[str, object]]:
    if not OUTPUT_FILE.exists():
        return []
    return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))


def save_records(records: list[dict[str, object]]) -> None:
    OUTPUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="从官方 HTML 分段表导入分数-位次数据")
    parser.add_argument("--province", required=True)
    parser.add_argument("--subject-type", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = extract_rows(fetch_text(args.url))
    if not rows:
        raise SystemExit("未从 HTML 提取到分数位次行")
    print(f"提取 {len(rows)} 行")
    print("样例：", rows[:5])

    if args.dry_run:
        return

    existing = load_existing()
    filtered = [
        item
        for item in existing
        if not (
            item.get("province") == args.province
            and item.get("subject_type") == args.subject_type
            and item.get("year") == args.year
            and item.get("source_type") == "exam_official"
        )
    ]
    for score, rank in rows:
        filtered.append(
            {
                "year": args.year,
                "province": args.province,
                "subject_type": args.subject_type,
                "score": score,
                "rank": rank,
                "source": args.source,
                "source_type": "exam_official",
                "url": args.url,
            }
        )
    save_records(filtered)
    print(f"已写入：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
