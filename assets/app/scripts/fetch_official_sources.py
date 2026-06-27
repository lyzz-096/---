from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "official_sources"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GaokaoAdvisor/0.2"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        self._href = attr_map.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append(("".join(self._text).strip(), self._href))
            self._href = None
            self._text = []


def http_get(url: str, timeout: int = 15) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def decode_html(payload: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    return payload.decode("utf-8", errors="replace")


def safe_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    return value[:120] or "download"


def download_links(province: str, url: str, keywords: list[str], out_dir: Path) -> list[dict[str, str]]:
    province_dir = out_dir / province
    province_dir.mkdir(parents=True, exist_ok=True)
    html = decode_html(http_get(url))
    (province_dir / "source_page.html").write_text(html, encoding="utf-8")

    parser = LinkParser()
    parser.feed(html)
    downloads: list[dict[str, str]] = []
    for text, href in parser.links:
        full_url = urljoin(url, href)
        haystack = f"{text} {href}"
        if keywords and not any(keyword in haystack for keyword in keywords):
            continue
        if not re.search(r"\.(pdf|xls|xlsx|zip)(?:$|\?)", full_url, flags=re.I):
            continue
        suffix_match = re.search(r"\.(pdf|xls|xlsx|zip)", full_url, flags=re.I)
        suffix = suffix_match.group(0).lower() if suffix_match else ".bin"
        target = province_dir / f"{safe_name(text)}{suffix}"
        payload = http_get(full_url, timeout=30)
        target.write_bytes(payload)
        downloads.append({"title": text, "url": full_url, "path": str(target), "bytes": str(len(payload))})
    (province_dir / "downloads.json").write_text(json.dumps(downloads, ensure_ascii=False, indent=2), encoding="utf-8")
    return downloads


def main() -> None:
    parser = argparse.ArgumentParser(description="从官方页面抓取高考资源附件")
    parser.add_argument("--province", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--keywords", default="", help="逗号分隔关键词，例如 分数分布,一分一段")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    keywords = [item.strip() for item in args.keywords.replace("，", ",").split(",") if item.strip()]
    downloads = download_links(args.province, args.url, keywords, Path(args.out_dir))
    print(f"下载 {len(downloads)} 个附件")
    for item in downloads:
        print(f"- {item['title']} -> {item['path']}")


if __name__ == "__main__":
    main()
