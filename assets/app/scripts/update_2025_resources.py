from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DB = APP_ROOT / "data" / "admission_clean.db"
DEFAULT_SOURCE_DIR = APP_ROOT / "data" / "official_sources"
WORK_DIR = Path(__file__).resolve().parent.parent / ".runtime" / "resource_update"


def inspect_db(db_path: Path) -> dict:
    if not db_path.exists():
        return {"exists": False, "path": str(db_path)}
    conn = sqlite3.connect(str(db_path))
    try:
        total = conn.execute("SELECT COUNT(*) FROM admission").fetchone()[0]
        coverage = conn.execute(
            """
            SELECT province, year, COUNT(*) AS total,
                   SUM(CASE WHEN rank > 0 THEN 1 ELSE 0 END) AS with_rank
            FROM admission
            GROUP BY province, year
            ORDER BY province, year
            """
        ).fetchall()
        latest = conn.execute(
            """
            SELECT province, MAX(year) AS latest_year, COUNT(*) AS total
            FROM admission
            GROUP BY province
            ORDER BY province
            """
        ).fetchall()
    finally:
        conn.close()
    return {
        "exists": True,
        "path": str(db_path),
        "size_mb": round(db_path.stat().st_size / 1024 / 1024, 1),
        "total": total,
        "coverage": coverage,
        "latest": latest,
        "latest_2025_provinces": [row[0] for row in latest if row[1] == 2025],
        "not_latest_2025_provinces": [row[0] for row in latest if row[1] != 2025],
    }


def print_inspection(report: dict) -> None:
    if not report["exists"]:
        print(f"数据库不存在：{report['path']}")
        return
    print(f"数据库：{report['path']}")
    print(f"大小：{report['size_mb']} MB")
    print(f"总记录：{report['total']:,}")
    print()
    print("已是 2025 最新年份的省份：")
    print("、".join(report["latest_2025_provinces"]) or "无")
    print()
    print("仍不是 2025 最新年份的省份：")
    print("、".join(report["not_latest_2025_provinces"]) or "无")
    print()
    print("按省份/年份分布：")
    for province, year, total, with_rank in report["coverage"]:
        print(f"  {province:8s} {year}: {total:8,d} 条，有位次 {with_rank or 0:8,d}")


def run_python(script: Path, args: list[str], env: dict[str, str]) -> None:
    command = [sys.executable, str(script), *args]
    print("运行：", " ".join(command))
    subprocess.run(command, check=True, env=env)


def build_and_clean(source_dir: Path, app_root: Path, work_dir: Path) -> Path:
    build_script = app_root / "scripts" / "build_db.py"
    clean_script = app_root / "scripts" / "clean_data.py"
    if not build_script.exists() or not clean_script.exists():
        raise FileNotFoundError("找不到本地脚本 scripts/build_db.py 或 scripts/clean_data.py")
    if not source_dir.exists():
        raise FileNotFoundError(f"源数据目录不存在：{source_dir}")

    excel_files = list(source_dir.rglob("*.xls")) + list(source_dir.rglob("*.xlsx"))
    if not excel_files:
        raise FileNotFoundError(f"源数据目录里没有 .xls/.xlsx 文件：{source_dir}")

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_db = work_dir / "admission_2025_raw.db"
    clean_db = work_dir / "admission_2025_clean.db"
    for path in (raw_db, clean_db):
        if path.exists():
            path.unlink()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    run_python(build_script, ["--data-dir", str(source_dir), "--db-path", str(raw_db)], env)
    run_python(clean_script, ["--src", str(raw_db), "--dst", str(clean_db)], env)
    return clean_db


def replace_database(new_db: Path, target_db: Path, dry_run: bool) -> Path | None:
    if not new_db.exists():
        raise FileNotFoundError(f"新数据库不存在：{new_db}")
    if dry_run:
        print(f"[dry-run] 不替换目标库。新库位于：{new_db}")
        return None

    target_db.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target_db.with_suffix(f".backup-{timestamp}.db")
    if target_db.exists():
        shutil.copy2(target_db, backup)
        print(f"已备份旧库：{backup}")
    shutil.copy2(new_db, target_db)
    print(f"已替换目标库：{target_db}")
    return backup if target_db.exists() else None


def parse_provinces(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("，", ",").replace("、", ",").split(",") if item.strip()]


def merge_database_by_province(new_db: Path, target_db: Path, provinces: list[str], dry_run: bool) -> Path | None:
    if not new_db.exists():
        raise FileNotFoundError(f"新数据库不存在：{new_db}")
    if not target_db.exists():
        raise FileNotFoundError(f"目标数据库不存在：{target_db}")
    if not provinces:
        raise ValueError("增量合并必须指定省份，例如 --merge-provinces 浙江,湖北")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target_db.with_suffix(f".backup-{timestamp}.db")
    if dry_run:
        print(f"[dry-run] 将按省份增量合并：{'、'.join(provinces)}")
        _print_merge_preview(new_db, target_db, provinces)
        return None

    shutil.copy2(target_db, backup)
    print(f"已备份旧库：{backup}")
    _merge_rows(new_db, target_db, provinces)
    print(f"已按省份增量合并：{'、'.join(provinces)}")
    return backup


def _print_merge_preview(new_db: Path, target_db: Path, provinces: list[str]) -> None:
    new_conn = sqlite3.connect(str(new_db))
    target_conn = sqlite3.connect(str(target_db))
    try:
        for province in provinces:
            new_count = new_conn.execute(
                "SELECT COUNT(*) FROM admission WHERE province LIKE ? AND year=2025",
                (f"%{province}%",),
            ).fetchone()[0]
            old_2025 = target_conn.execute(
                "SELECT COUNT(*) FROM admission WHERE province LIKE ? AND year=2025",
                (f"%{province}%",),
            ).fetchone()[0]
            old_all = target_conn.execute(
                "SELECT COUNT(*) FROM admission WHERE province LIKE ?",
                (f"%{province}%",),
            ).fetchone()[0]
            print(f"  {province}: 新库2025 {new_count:,} 条；目标库现有2025 {old_2025:,} 条；目标库全部 {old_all:,} 条")
    finally:
        new_conn.close()
        target_conn.close()


def _merge_rows(new_db: Path, target_db: Path, provinces: list[str]) -> None:
    target_conn = sqlite3.connect(str(target_db))
    target_cols = [row[1] for row in target_conn.execute("PRAGMA table_info(admission)").fetchall()]
    if not target_cols:
        target_conn.close()
        raise RuntimeError("目标库 admission 表不存在")

    try:
        target_conn.execute("ATTACH DATABASE ? AS incoming", (str(new_db),))
        incoming_cols = [row[1] for row in target_conn.execute("PRAGMA incoming.table_info(admission)").fetchall()]
        common_cols = [col for col in target_cols if col in incoming_cols]
        if not common_cols:
            raise RuntimeError("新库和目标库没有可合并字段")

        target_col_sql = ", ".join(f'"{col}"' for col in common_cols)
        incoming_col_sql = ", ".join(f'incoming.admission."{col}"' for col in common_cols)
        for province in provinces:
            pattern = f"%{province}%"
            target_conn.execute(
                "DELETE FROM admission WHERE province LIKE ? AND year=2025",
                (pattern,),
            )
            target_conn.execute(
                f"""
                INSERT INTO admission ({target_col_sql})
                SELECT {incoming_col_sql}
                FROM incoming.admission
                WHERE incoming.admission.province LIKE ? AND incoming.admission.year=2025
                """,
                (pattern,),
            )
        target_conn.commit()
    finally:
        target_conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="更新高考志愿本地录取资源库到 2025 数据")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="2025 官方 Excel 数据目录")
    parser.add_argument("--app-root", default=str(APP_ROOT), help="应用根目录")
    parser.add_argument("--target-db", default=str(DEFAULT_TARGET_DB), help="要替换的 admission_clean.db")
    parser.add_argument("--inspect", action="store_true", help="只检查当前数据库覆盖")
    parser.add_argument("--dry-run", action="store_true", help="构建并清洗，但不替换目标库")
    parser.add_argument("--merge-provinces", default="", help="按省份增量合并 2025 记录，例如 浙江,湖北")
    parser.add_argument("--replace-all", action="store_true", help="全量替换目标库。危险操作，只有源目录是完整全量库时使用")
    parser.add_argument("--json", action="store_true", help="检查结果输出 JSON")
    args = parser.parse_args()

    target_db = Path(args.target_db)
    if args.inspect:
        report = inspect_db(target_db)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_inspection(report)
        return 0

    source_dir = Path(args.source_dir)
    app_root = Path(args.app_root)
    clean_db = build_and_clean(source_dir, app_root, WORK_DIR)
    print()
    print("新库检查：")
    print_inspection(inspect_db(clean_db))
    merge_provinces = parse_provinces(args.merge_provinces)
    if merge_provinces:
        merge_database_by_province(clean_db, target_db, merge_provinces, args.dry_run)
    elif args.replace_all:
        replace_database(clean_db, target_db, args.dry_run)
    else:
        print()
        print("未执行替换：逐步完善数据库请使用 --merge-provinces 指定省份。")
        print("示例：python scripts\\update_2025_resources.py --source-dir \".\\data\\official_sources\\浙江\" --merge-provinces 浙江 --dry-run")
        print("只有源目录是全国完整全量数据时，才使用 --replace-all。")
    print()
    print("目标库检查：")
    print_inspection(inspect_db(target_db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
