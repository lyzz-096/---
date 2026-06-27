from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def render_report(template_path: Path, data_path: Path, output_path: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    report_data = json.loads(data_path.read_text(encoding="utf-8"))
    encoded = json.dumps(report_data, ensure_ascii=False, indent=6)
    html, count = re.subn(
        r"const reportData = \{.*?\n    \};",
        f"const reportData = {encoded};",
        template,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit("template does not contain a replaceable reportData block")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render gaokao final HTML report from reportData JSON.")
    parser.add_argument("--template", required=True, help="Path to report_template/index.html")
    parser.add_argument("--data", required=True, help="Path to reportData JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()
    render_report(Path(args.template), Path(args.data), Path(args.output))


if __name__ == "__main__":
    main()
