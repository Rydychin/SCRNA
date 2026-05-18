import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# These paths come from Docker Compose during normal pipeline runs.
QC_DIR = Path(os.environ.get("QC_DIR", "/data/intermediate/qc"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/intermediate/alignment"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs"))
ALIGNER = os.environ.get("ALIGNER", "mock")
SAMPLE_ID = os.environ.get("SAMPLE_ID", "sample")


# Create output folders before writing metrics or logs.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(level, message, **fields):
    # JSON logs are easy to read now and easy to parse later.
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "stage": "alignment",
        "sample_id": SAMPLE_ID,
        "level": level,
        "message": message,
        **fields,
    }

    print(json.dumps(record), flush=True)

    with open(LOG_DIR / "alignment.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def main():
    start_time = time.monotonic()

    # Log the config we are about to use for this alignment stage.
    log(
        "info",
        "Alignment stage started",
        event_type="stage_started",
        qc_dir=str(QC_DIR),
        output_dir=str(OUTPUT_DIR),
        aligner=ALIGNER,
    )

    qc_success_file = QC_DIR / "_SUCCESS"
    qc_metrics_file = QC_DIR / "qc_metrics.csv"

    # The alignment stage should only run after QC has completed successfully.
    if not qc_success_file.exists():
        log(
            "error",
            "QC success marker is missing",
            event_type="input_missing",
            expected_file=str(qc_success_file),
        )
        sys.exit(1)

    # The alignment stage uses the QC read counts as its input.
    if not qc_metrics_file.exists():
        log(
            "error",
            "QC metrics file is missing",
            event_type="input_missing",
            expected_file=str(qc_metrics_file),
        )
        sys.exit(1)

    qc_metrics = pd.read_csv(qc_metrics_file)

    total_reads = int(qc_metrics["reads"].sum())

    # No reads means there is nothing to align.
    if total_reads <= 0:
        log("error", "No reads available after QC", event_type="invalid_input")
        sys.exit(1)

    # This is a mock alignment step: it makes realistic-looking metrics without
    # running a real aligner like STARsolo or Cell Ranger.
    mapped_reads = int(total_reads * 0.82)
    mapping_rate = mapped_reads / total_reads

    # Keep the cell estimate simple for now so the demo pipeline stays lightweight.
    estimated_cells = max(1, total_reads // 1000)
    mean_reads_per_cell = total_reads / estimated_cells

    metrics = {
        "sample_id": SAMPLE_ID,
        "aligner": ALIGNER,
        "total_reads": total_reads,
        "mapped_reads": mapped_reads,
        "mapping_rate": round(mapping_rate, 4),
        "estimated_cells": estimated_cells,
        "median_genes_per_cell": 1200,
        "mean_reads_per_cell": round(mean_reads_per_cell, 2),
    }

    # Write the alignment summary for humans and downstream pipeline steps.
    pd.DataFrame([metrics]).to_csv(
        OUTPUT_DIR / "alignment_metrics.csv",
        index=False,
    )

    with open(OUTPUT_DIR / "alignment_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Also create a tidy table that is easier to load into a database.
    db_rows = []

    for metric_name, metric_value in metrics.items():
        if metric_name == "sample_id":
            continue

        db_rows.append(
            {
                "sample_id": SAMPLE_ID,
                "metric_name": metric_name,
                "metric_value": metric_value,
            }
        )

    pd.DataFrame(db_rows).to_csv(
        OUTPUT_DIR / "db_metrics.csv",
        index=False,
    )

    # The report stage waits for this marker before it starts.
    (OUTPUT_DIR / "_SUCCESS").write_text("alignment complete\n")

    log(
        "info",
        "Alignment stage complete",
        event_type="stage_completed",
        aligner=ALIGNER,
        total_reads=total_reads,
        mapped_reads=mapped_reads,
        mapping_rate=round(mapping_rate, 4),
        duration_seconds=round(time.monotonic() - start_time, 3),
    )


if __name__ == "__main__":
    main()
