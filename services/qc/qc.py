import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# These paths mostly come from Docker Compose, but the defaults make the script
# easier to run by hand if needed.
INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/data/fastq"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/intermediate/qc"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs"))
MIN_READS = int(os.environ.get("MIN_READS", "1"))
SAMPLE_ID = os.environ.get("SAMPLE_ID", "sample")


# Make sure the folders exist before we try to write metrics or logs.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(level, message, **fields):
    # Keep logs as JSON so both people and programs can read them later.
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "stage": "qc",
        "sample_id": SAMPLE_ID,
        "level": level,
        "message": message,
        **fields,
    }

    print(json.dumps(record), flush=True)

    with open(LOG_DIR / "qc.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def open_fastq(path):
    # FASTQ files may be plain text or gzipped, so open them the right way.
    if path.suffix == ".gz":
        return gzip.open(path, "rt")

    return open(path, "r")


def inspect_fastq(path):
    # Track the basic QC numbers we care about for this one file.
    reads = 0
    total_bases = 0
    total_quality = 0

    with open_fastq(path) as handle:
        while True:
            # A FASTQ read is always four lines: header, sequence, plus, quality.
            header = handle.readline()
            sequence = handle.readline()
            plus = handle.readline()
            quality = handle.readline()

            # Empty header means we reached the end of the file cleanly.
            if not header:
                break

            # If any of the four lines are missing, the FASTQ is broken.
            if not sequence or not plus or not quality:
                raise ValueError(f"Incomplete FASTQ record in {path.name}")

            # FASTQ headers should start with @.
            if not header.startswith("@"):
                raise ValueError(f"Invalid FASTQ header in {path.name}")

            sequence = sequence.strip()
            quality = quality.strip()

            # Count this read and add its bases and quality scores to the totals.
            reads += 1
            total_bases += len(sequence)
            total_quality += sum(ord(char) - 33 for char in quality)

    # Avoid dividing by zero in case a file is empty.
    mean_read_length = total_bases / reads if reads else 0
    mean_quality = total_quality / total_bases if total_bases else 0

    # This is the simple pass/fail check for this stage.
    status = "pass" if reads >= MIN_READS else "fail"

    return {
        "file": path.name,
        "reads": reads,
        "total_bases": total_bases,
        "mean_read_length": round(mean_read_length, 2),
        "mean_quality": round(mean_quality, 2),
        "status": status,
    }


def main():
    start_time = time.monotonic()

    # First log line tells us the stage started and what settings it received.
    log(
        "info",
        "QC stage started",
        event_type="stage_started",
        input_dir=str(INPUT_DIR),
        output_dir=str(OUTPUT_DIR),
        min_reads=MIN_READS,
    )

    # Pick up the common FASTQ extensions, both compressed and uncompressed.
    fastq_files = sorted(
        list(INPUT_DIR.glob("*.fastq"))
        + list(INPUT_DIR.glob("*.fastq.gz"))
        + list(INPUT_DIR.glob("*.fq"))
        + list(INPUT_DIR.glob("*.fq.gz"))
    )

    # No inputs means the pipeline cannot do anything useful, so fail fast.
    if not fastq_files:
        log(
            "error",
            "No FASTQ files found",
            event_type="input_missing",
            input_dir=str(INPUT_DIR),
        )
        sys.exit(1)

    results = []

    for path in fastq_files:
        try:
            # Inspect each file separately so the log can say exactly what failed.
            metrics = inspect_fastq(path)
            results.append(metrics)

            log(
                "info",
                "FASTQ inspected",
                event_type="fastq_inspected",
                file=path.name,
                reads=metrics["reads"],
                mean_quality=metrics["mean_quality"],
            )

        except Exception as error:
            # Stop the stage on validation errors instead of passing bad data along.
            log(
                "error",
                "FASTQ validation failed",
                event_type="fastq_validation_failed",
                file=path.name,
                error=str(error),
            )
            sys.exit(1)

    # Save the same metrics in CSV and JSON so later steps have easy options.
    df = pd.DataFrame(results)

    df.to_csv(OUTPUT_DIR / "qc_metrics.csv", index=False)

    with open(OUTPUT_DIR / "qc_metrics.json", "w") as f:
        json.dump(results, f, indent=2)

    # If any file missed the minimum-read cutoff, the whole QC stage fails.
    if (df["status"] == "fail").any():
        failed_files = df[df["status"] == "fail"]["file"].tolist()

        log(
            "error",
            "One or more FASTQ files failed QC",
            event_type="qc_threshold_failed",
            failed_files=failed_files,
        )

        sys.exit(1)

    # The success marker is how Docker Compose knows this stage finished cleanly.
    (OUTPUT_DIR / "_SUCCESS").write_text("qc complete\n")

    log(
        "info",
        "QC stage complete",
        event_type="stage_completed",
        files=len(results),
        duration_seconds=round(time.monotonic() - start_time, 3),
    )


if __name__ == "__main__":
    main()
