from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import Dict

from gaokao_tool.service import build_profile, generate_recommendations, generate_recommendation_response, render_summary
from gaokao_tool.service import estimate_rank
from gaokao_tool.final_report import build_report_data, export_final_report, render_final_report_html
from gaokao_tool.web import render_app_html
from gaokao_tool.web_research import execute_research, render_research_evidence


PROMPTS = [
    ("province", "省份"),
    ("subject_type", "科类/选科（如 物理类）"),
    ("score", "分数"),
    ("rank", "位次"),
    ("preferred_majors", "偏好专业，多个用英文逗号分隔"),
    ("excluded_majors", "排斥专业，多个用英文逗号分隔"),
    ("preferred_regions", "城市偏好，多个用英文逗号分隔"),
    ("career_goal", "核心诉求（如 就业、考公、稳定、高薪）"),
    ("family_background", "家庭资源标签（如 电网、医生、普通家庭）"),
    ("accept_postgraduate", "是否接受考研（y/n）"),
]


def collect_cli_payload() -> Dict[str, str]:
    payload: Dict[str, str] = {}
    print("请输入考生信息，直接回车可留空。第一版必须填写省份、科类/选科、位次。")
    for key, label in PROMPTS:
        payload[key] = input(f"{label}: ").strip()
    return payload


def run_cli() -> None:
    payload = collect_cli_payload()
    profile, recommendations, diagnostics = generate_recommendation_response(payload)
    print()
    print(render_summary(profile, recommendations, diagnostics))


class RequestHandler(BaseHTTPRequestHandler):
    def _send_html(self, html: str, status_code: int = 200) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: Dict | list, status_code: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/recommend"}:
            self._send_html(render_app_html())
            return
        if path == "/health":
            self._send_json({"ok": True})
            return
        if path == "/final-report":
            self._send_html(render_app_html())
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/recommend", "/rank", "/research", "/final-report", "/export-report"}:
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
            if path == "/rank":
                province = payload.get("province", "").strip()
                subject_type = payload.get("subject_type", "").strip()
                score = int(payload.get("score", ""))
                rank, source = estimate_rank(province, subject_type, score)
                self._send_json({"rank": rank, "source": source})
                return

            profile, recommendations, diagnostics = generate_recommendation_response(payload)
            if path == "/final-report":
                report_data = build_report_data(profile, recommendations)
                self._send_html(render_final_report_html(report_data))
                return

            if path == "/export-report":
                output_path = export_final_report(profile, recommendations)
                self._send_json(
                    {
                        "ok": True,
                        "path": str(output_path),
                        "fileUrl": output_path.resolve().as_uri(),
                        "filename": output_path.name,
                    }
                )
                return

            if path == "/research":
                schools = list(dict.fromkeys(item.school_name for item in recommendations))
                evidence = execute_research(profile, schools)
                self._send_json(
                    {
                        "profile": profile.__dict__,
                        "evidence": [item.__dict__ for item in evidence],
                        "summary": render_research_evidence(evidence),
                    }
                )
                return

            response = {
                "profile": profile.__dict__,
                "recommendations": [item.__dict__ for item in recommendations],
                "diagnostics": diagnostics,
                "summary": render_summary(profile, recommendations, diagnostics),
            }
            self._send_json(response)
        except (KeyError, TypeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status_code=400)


def run_api(port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), RequestHandler)
    print(f"API 已启动：http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="高考志愿全自动咨询系统")
    parser.add_argument("--api", action="store_true", help="启动本地 HTTP API")
    parser.add_argument("--port", type=int, default=8765, help="API 端口")
    args = parser.parse_args()

    if args.api:
        run_api(args.port)
        return
    run_cli()


if __name__ == "__main__":
    main()
