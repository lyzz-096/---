from __future__ import annotations

import argparse
import json
from pathlib import Path


REGISTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "source_registry.json"


def load_registry() -> dict[str, list[dict[str, object]]]:
    if not REGISTRY_FILE.exists():
        return {}
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def save_registry(registry: dict[str, list[dict[str, object]]]) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("，", ",").replace("、", ",").split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="向高考志愿资源网站库追加已验证来源")
    parser.add_argument("--province", required=True, help="省份，例如 浙江")
    parser.add_argument("--purpose", required=True, help="用途，逗号分隔，例如 分数转位次,高校专业录取数据")
    parser.add_argument("--title", required=True, help="来源标题")
    parser.add_argument("--url", required=True, help="来源 URL")
    parser.add_argument("--source-type", default="exam_official", help="exam_official/university/sunshine/third_party")
    parser.add_argument("--snippet", default="", help="来源说明")
    parser.add_argument("--hints", default="", help="命中关键词，逗号分隔")
    args = parser.parse_args()

    registry = load_registry()
    sources = registry.setdefault(args.province, [])
    if any(str(item.get("url", "")).strip() == args.url for item in sources):
        print(f"已存在：{args.url}")
        return

    sources.append(
        {
            "purpose": parse_csv(args.purpose),
            "title": args.title.strip(),
            "url": args.url.strip(),
            "source_type": args.source_type.strip(),
            "snippet": args.snippet.strip(),
            "query_hints": parse_csv(args.hints),
        }
    )
    save_registry(registry)
    print(f"已添加：{args.province} / {args.title}")


if __name__ == "__main__":
    main()
