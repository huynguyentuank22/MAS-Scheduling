#!/usr/bin/env python
"""Generate a concise validation-metrics report from benchmark metrics.json."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


_FIELDS = [
    "success_rate",
    "mean_score",
    "agent_output_schema_valid_rate",
    "parse_failure_rate",
    "repair_success_rate",
    "invalid_artifact_ref_rate",
    "memory_validation_failure_rate",
    "unsupported_lesson_rate",
    "overgeneralized_memory_rate",
    "curator_accept_rate",
    "curator_reject_rate",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report validation metrics from synthetic benchmark output")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("experiments/stabilization_sprint_20260508"),
        help="Directory containing metrics.json",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=None,
        help="CSV output path (default: <run-dir>/validation_metrics_report.csv)",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=None,
        help="Markdown output path (default: <run-dir>/validation_metrics_report.md)",
    )
    return parser.parse_args()


def load_metrics(run_dir: Path) -> dict[str, Any]:
    metrics_path = run_dir / "metrics.json"
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def build_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant, data in metrics.items():
        row = {"variant": variant}
        for field in _FIELDS:
            row[field] = data.get(field, 0.0)
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["variant", *_FIELDS]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    headers = ["Variant", *[f.replace("_", " ") for f in _FIELDS]]
    lines: list[str] = []
    lines.append("# Validation Metrics Report")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        values = [str(row["variant"])]
        for field in _FIELDS:
            value = row.get(field, 0.0)
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    rows = build_rows(load_metrics(args.run_dir))
    csv_out = args.csv_out or (args.run_dir / "validation_metrics_report.csv")
    md_out = args.md_out or (args.run_dir / "validation_metrics_report.md")
    write_csv(rows, csv_out)
    write_markdown(rows, md_out)
    print(f"CSV written: {csv_out}")
    print(f"Markdown written: {md_out}")


if __name__ == "__main__":
    main()
