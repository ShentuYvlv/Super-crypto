from __future__ import annotations

from super_crypto.common.paths import REPORT_ROOT


def list_reports() -> list[dict]:
    reports = []
    if not REPORT_ROOT.exists():
        return reports
    for path in REPORT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        reports.append(
            {
                "report_type": path.suffix.lstrip("."),
                "path": str(path),
                "generated_at": path.stat().st_mtime,
                "hash": path.stem,
            }
        )
    return sorted(reports, key=lambda item: item["generated_at"], reverse=True)
