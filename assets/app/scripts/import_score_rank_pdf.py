from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pdfplumber


OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "score_rank_overrides.json"


def load_existing() -> list[dict[str, object]]:
    if not OUTPUT_FILE.exists():
        return []
    return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))


def save_records(records: list[dict[str, object]]) -> None:
    OUTPUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_rows_from_pdf(pdf_path: Path) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                header_rows = table[:2] if table else []
                combined_header = []
                max_cols = max((len(row) for row in header_rows), default=0)
                for col in range(max_cols):
                    combined_header.append("".join(str(row[col] or "").replace("\n", "") for row in header_rows if col < len(row)))
                score_idx = next((idx for idx, cell in enumerate(combined_header) if "分数" in cell or "总分" in cell), 0)
                rank_idx = next((idx for idx, cell in enumerate(combined_header) if "累计" in cell), None)
                if rank_idx is not None:
                    data_start = 2 if len(table) > 1 and any("累计" in str(cell or "") for cell in table[1]) else 1
                    for row in table[data_start:]:
                        if score_idx >= len(row) or rank_idx >= len(row):
                            continue
                        score = _first_int(row[score_idx])
                        rank = _first_int(row[rank_idx])
                        if score is not None and rank is not None and 100 <= score <= 750 and rank > 0:
                            rows.append((score, rank))
                    continue

                for row in table:
                    numbers = []
                    for cell in row:
                        if not cell:
                            continue
                        cleaned = re.sub(r"[,\s]", "", str(cell))
                        if re.fullmatch(r"\d+", cleaned):
                            numbers.append(int(cleaned))
                    if len(numbers) >= 2:
                        score = numbers[0]
                        rank = numbers[-1]
                        if 100 <= score <= 750 and rank > 0:
                            rows.append((score, rank))

            if not tables:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    nums = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", line)]
                    if len(nums) >= 2 and 100 <= nums[0] <= 750 and nums[-1] > 0:
                        rows.append((nums[0], nums[-1]))
    return sorted(set(rows), reverse=True)


def _first_int(value: object) -> int | None:
    if value is None:
        return None
    matches = re.findall(r"\d[\d,]*", str(value))
    if not matches:
        return None
    return int(matches[0].replace(",", ""))


def upsert_records(
    existing: list[dict[str, object]],
    province: str,
    subject_type: str,
    year: int,
    rows: list[tuple[int, int]],
    source: str,
    url: str,
) -> list[dict[str, object]]:
    filtered = [
        item
        for item in existing
        if not (
            item.get("province") == province
            and item.get("subject_type") == subject_type
            and item.get("year") == year
            and item.get("source_type") == "exam_official"
        )
    ]
    for score, rank in rows:
        filtered.append(
            {
                "year": year,
                "province": province,
                "subject_type": subject_type,
                "score": score,
                "rank": rank,
                "source": source,
                "source_type": "exam_official",
                "url": url,
            }
        )
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="从官方 PDF 分数分布表导入分数-位次数据")
    parser.add_argument("--province", required=True)
    parser.add_argument("--subject-type", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = extract_rows_from_pdf(Path(args.pdf))
    if not rows:
        raise SystemExit("未从 PDF 提取到分数位次行")
    print(f"提取 {len(rows)} 行")
    print("样例：", rows[:5])

    if args.dry_run:
        return

    existing = load_existing()
    updated = upsert_records(
        existing,
        args.province,
        args.subject_type,
        args.year,
        rows,
        args.source,
        args.url,
    )
    save_records(updated)
    print(f"已写入：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
