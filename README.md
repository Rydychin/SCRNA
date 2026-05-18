# Containerized scRNA-seq Analysis Pipeline

This project implements a Docker Compose workflow for a mock single-cell RNA-seq analysis pipeline. It is designed to show how a manual analysis can be split into reproducible, containerized stages with shared inputs, intermediate outputs, structured logs, and final report artifacts.

The pipeline has three services:

```text
FASTQ files -> QC -> Alignment -> Report
```

Each stage runs in its own container and passes data through mounted folders.

## Architecture

```text
scrna-pipeline/
├── docker-compose.yml
├── .env.example
├── services/
│   ├── qc/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── qc.py
│   ├── alignment/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── align.py
│   └── report/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── report.py
├── data/
│   ├── fastq/          # input FASTQ files
│   ├── reference/      # reference files for a production aligner
│   ├── intermediate/   # stage-to-stage outputs
│   └── output/         # final reports and metrics
└── logs/               # structured JSONL logs
```

`docker-compose.yml` controls build order, volume mounts, environment variables, resource limits, health checks, and stage dependencies.

## Pipeline Stages

**QC**

Reads FASTQ files from `data/fastq/`, validates FASTQ record structure, counts reads, calculates total bases, mean read length, and mean quality.

Outputs:

```text
data/intermediate/qc/qc_metrics.csv
data/intermediate/qc/qc_metrics.json
data/intermediate/qc/_SUCCESS
```

**Alignment**

Waits for QC to complete successfully. This stage is currently a mock implementation that reads QC metrics and produces alignment-style metrics such as mapped reads, mapping rate, estimated cells, and median genes per cell.

Outputs:

```text
data/intermediate/alignment/alignment_metrics.csv
data/intermediate/alignment/alignment_metrics.json
data/intermediate/alignment/db_metrics.csv
data/intermediate/alignment/_SUCCESS
```

**Report**

Waits for alignment to complete successfully. It creates an HTML summary report and copies database-ready metrics into the final output folder.

Outputs:

```text
data/output/report.html
data/output/db_metrics.csv
data/output/_SUCCESS
```

## Configuration

Create a local `.env` file from the template:

```bash
cp .env.example .env
```

Main variables:

```env
SAMPLE_ID=SRR8387812
ALIGNER=mock
MIN_READS=1

QC_CPUS=1
QC_MEMORY=1g
ALIGN_CPUS=2
ALIGN_MEMORY=4g
REPORT_CPUS=1
REPORT_MEMORY=1g
```

`.env` is used for local runtime configuration and should not be committed. `.env.example` documents the expected settings.

## Quickstart

Place FASTQ files in:

```text
data/fastq/
```

For a tiny smoke test, create a valid FASTQ file:

```bash
cat > data/fastq/sample_R1.fastq <<'EOF'
@read1
ACGTACGTACGT
+
FFFFFFFFFFFF
@read2
TGCATGCATGCA
+
FFFFFFFFFFFF
EOF
```

Run the full pipeline:

```bash
docker compose up --build
```

Run one stage:

```bash
docker compose up --build qc
docker compose up --build alignment
docker compose up --build report
```

After a successful run, open:

```text
data/output/report.html
```

The database-ready metrics are written to:

```text
data/output/db_metrics.csv
```

Example:

```csv
sample_id,metric_name,metric_value
SRR8387812,aligner,mock
SRR8387812,total_reads,2
SRR8387812,mapped_reads,1
SRR8387812,mapping_rate,0.5
SRR8387812,estimated_cells,1
SRR8387812,median_genes_per_cell,1200
SRR8387812,mean_reads_per_cell,2.0
```

## Using SRR8387812

The prompt recommends SRA run `SRR8387812`. With SRA Toolkit installed:

```bash
mkdir -p sra_download
cd sra_download
fasterq-dump --split-files SRR8387812
```

For faster local testing, make a small subset. FASTQ records are 4 lines each, so 4000 lines equals 1000 reads:

```bash
head -n 4000 SRR8387812_1.fastq > ../data/fastq/SRR8387812_subset_R1.fastq
head -n 4000 SRR8387812_2.fastq > ../data/fastq/SRR8387812_subset_R2.fastq
```

## Logging and Failure Behavior

Each stage writes structured JSONL logs:

```text
logs/qc.jsonl
logs/alignment.jsonl
logs/report.jsonl
```

Log records include `time`, `stage`, `sample_id`, `level`, `message`, and `event_type`. All stages emit `stage_started` and `stage_completed` events. QC also emits one `fastq_inspected` event per FASTQ file.

Each stage validates required inputs before continuing. For example:

- QC fails if no FASTQ files are found or a FASTQ record is malformed.
- Alignment fails if QC did not create `_SUCCESS`.
- Report fails if alignment did not create `_SUCCESS`.

Failures exit with a non-zero status so Docker Compose does not continue the pipeline.

## Best Practices Included

- Three independent containers, one per pipeline stage.
- Shared folders for inputs, intermediates, outputs, and logs.
- `depends_on` with `service_completed_successfully` for stage ordering.
- Read-only mounts for raw FASTQ and reference inputs.
- Slim Python base images.
- Pinned Python dependencies in `requirements.txt`.
- Containers run as a non-root user.
- Structured logs for debugging and monitoring.
- `_SUCCESS` marker files for completed stages.
- CPU and memory settings configured through environment variables.
- `.env.example` provided as a safe configuration template.
- Generated data, logs, and local `.env` ignored through `.gitignore`.

## Limitations

The alignment stage is mocked. It does not perform real biological alignment 
against a reference genome.

This is intentional for the screening project so the full Docker workflow 
can run quickly on a local machine. In production, the alignment container 
could be replaced with Cell Ranger, Kallisto, kb-python, STARsolo, or 
another approved scRNA-seq processing tool.
