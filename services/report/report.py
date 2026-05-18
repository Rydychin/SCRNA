import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# These folders are passed in by Docker Compose during normal runs.
QC_DIR = Path(os.environ.get("QC_DIR", "/data/intermediate/qc"))
ALIGNMENT_DIR = Path(os.environ.get("ALIGNMENT_DIR", "/data/intermediate/alignment"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/output"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs"))
SAMPLE_ID = os.environ.get("SAMPLE_ID", "sample")


# Make sure report output and logging folders are ready.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(level, message, **fields):
    # Log one JSON object per line so this stays easy to search and parse.
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "stage": "report",
        "sample_id": SAMPLE_ID,
        "level": level,
        "message": message,
        **fields,
    }

    print(json.dumps(record), flush=True)

    with open(LOG_DIR / "report.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def main():
    start_time = time.monotonic()

    # Start by recording where this report is reading from and writing to.
    log(
        "info",
        "Report stage started",
        event_type="stage_started",
        qc_dir=str(QC_DIR),
        alignment_dir=str(ALIGNMENT_DIR),
        output_dir=str(OUTPUT_DIR),
    )

    qc_metrics_file = QC_DIR / "qc_metrics.csv"
    alignment_metrics_file = ALIGNMENT_DIR / "alignment_metrics.json"
    db_metrics_file = ALIGNMENT_DIR / "db_metrics.csv"
    alignment_success_file = ALIGNMENT_DIR / "_SUCCESS"

    # The report is only useful if QC metrics are present.
    if not qc_metrics_file.exists():
        log(
            "error",
            "QC metrics file is missing",
            event_type="input_missing",
            expected_file=str(qc_metrics_file),
        )
        sys.exit(1)

    # Require the alignment success marker so we do not report on a half-run stage.
    if not alignment_success_file.exists():
        log(
            "error",
            "Alignment success marker is missing",
            event_type="input_missing",
            expected_file=str(alignment_success_file),
        )
        sys.exit(1)

    # This JSON file gives the report its main alignment summary numbers.
    if not alignment_metrics_file.exists():
        log(
            "error",
            "Alignment metrics file is missing",
            event_type="input_missing",
            expected_file=str(alignment_metrics_file),
        )
        sys.exit(1)

    # This CSV is copied to the final output folder for database loading.
    if not db_metrics_file.exists():
        log(
            "error",
            "Database metrics file is missing",
            event_type="input_missing",
            expected_file=str(db_metrics_file),
        )
        sys.exit(1)

    qc_metrics = pd.read_csv(qc_metrics_file)

    with open(alignment_metrics_file, "r") as f:
        alignment_metrics = json.load(f)

    # Build a small standalone HTML report that can be opened directly.
    html_report = f"""
        <!doctype html>
        <html>
        <head>
        <meta charset="utf-8">
        <title>scRNA-seq Pipeline Report - {SAMPLE_ID}</title>
        <style>
            body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.5;
            }}
            table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 24px;
            }}
            th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            }}
            th {{
            background-color: #f2f2f2;
            }}
            .metric {{
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 8px;
            }}
        </style>
        </head>
        <body>
        <h1>scRNA-seq Pipeline Report</h1>

        <p><strong>Sample ID:</strong> {SAMPLE_ID}</p>
        <p><strong>Generated:</strong> {datetime.now(timezone.utc).isoformat()}</p>

        <h2>QC Summary</h2>
        {qc_metrics.to_html(index=False)}

        <h2>Alignment Summary</h2>
        <div class="metric"><strong>Aligner:</strong> {alignment_metrics["aligner"]}</div>
        <div class="metric"><strong>Total Reads:</strong> {alignment_metrics["total_reads"]}</div>
        <div class="metric"><strong>Mapped Reads:</strong> {alignment_metrics["mapped_reads"]}</div>
        <div class="metric"><strong>Mapping Rate:</strong> {alignment_metrics["mapping_rate"]}</div>
        <div class="metric"><strong>Estimated Cells:</strong> {alignment_metrics["estimated_cells"]}</div>
        <div class="metric"><strong>Median Genes per Cell:</strong> {alignment_metrics["median_genes_per_cell"]}</div>
        <div class="metric"><strong>Mean Reads per Cell:</strong> {alignment_metrics["mean_reads_per_cell"]}</div>

        <h2>Database Metrics Output</h2>
        <p>The file <code>db_metrics.csv</code> contains database-ready metrics in a tidy row-based format.</p>
        </body>
        </html>
    """

    report_file = OUTPUT_DIR / "report.html"
    report_file.write_text(html_report)

    # Move the database-friendly metrics into the final output folder too.
    final_db_metrics_file = OUTPUT_DIR / "db_metrics.csv"
    pd.read_csv(db_metrics_file).to_csv(final_db_metrics_file, index=False)

    # Final success marker for the whole pipeline.
    (OUTPUT_DIR / "_SUCCESS").write_text("report complete\n")

    log(
        "info",
        "Report stage complete",
        event_type="stage_completed",
        report_file=str(report_file),
        db_metrics_file=str(final_db_metrics_file),
        duration_seconds=round(time.monotonic() - start_time, 3),
    )


if __name__ == "__main__":
    main()
