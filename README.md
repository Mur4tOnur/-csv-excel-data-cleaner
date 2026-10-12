# CSV & Excel Data Cleaner

A reliable Python tool designed to ingest, clean, validate, and report on CSV and XLSX tabular datasets.

## Problem Statement

Real-world datasets from CSV and Excel files frequently contain inconsistencies that hinder downstream processing and analysis:
- Messy, non-standardized column names (spaces, irregular casing, special characters).
- Full row duplicates inflating record counts.
- Missing, blank, or null values scattered across critical fields.
- Suspicious data patterns and anomalies (such as invalid data types, malformed numbers, or unexpected values).
- Lack of transparency and audit trails regarding transformations applied to raw data.

CSV & Excel Data Cleaner solves these problems by providing an automated, reproducible pipeline that cleans tabular files and produces comprehensive audit reports.

---

## Features Actually Implemented

- **Multi-Format Ingestion**: Safe loading of delimited files (`.csv`) and modern Excel spreadsheets (`.xlsx`) via pandas and openpyxl without mutating source files.
- **Column Standardization**: Converting column headers into clean, uniform snake_case (`whitespace stripped`, `lowercase conversion`, `spaces and hyphens replaced with underscores`, and strict `collision detection` to prevent accidental data loss).
- **Exact Duplicate Removal**: Identifying and removing exact duplicate rows where all columns match, preserving the first occurrence and original row order.
- **Data Quality & Validation**:
  - Missing-value analysis with count and percentage by column, plus total missing-cell metrics (empty strings are not treated as null).
  - Suspicious non-numeric value detection in designated columns.
  - Strict date validation using explicit strptime formats with zero ambiguous date guessing.
- **Cleaned Data Export**:
  - UTF-8 CSV export preserving non-ASCII/Unicode characters.
  - Openpyxl XLSX export.
  - Overwrite safety and source file collision protection.
- **Audit & Processing Reports**: Generating structured processing reports saved as human-readable UTF-8 JSON.
- **Command-Line Interface (CLI)**: Full terminal interface with clear flags, comprehensive error messages, and non-zero exit codes on failure.

---

## Current Development Status

> [!NOTE]
> **Status: Milestones 1 through 8 Complete (Production-Ready Release Scaffolding)**  
> All core modules, unit tests, end-to-end integration tests, synthetic demonstration data, and documentation have been implemented and verified.

---

## Environment Setup Instructions (macOS)

### Prerequisites

- macOS on Apple Silicon (or Intel)
- Python 3.13 (verified with Python 3.13.16)

### Virtual Environment Setup

To create a virtual environment (if setting up on a new machine):

```bash
python3 -m venv .venv
```

#### 1. Activate the Virtual Environment

From the project root directory, activate the virtual environment:

```bash
source .venv/bin/activate
```

To verify that the active Python interpreter points to the virtual environment:

```bash
which python
python --version
```

Expected output:
```
.../csv-excel-data-cleaner/.venv/bin/python
Python 3.13.16
```

#### 2. Install Dependencies

To install or sync dependencies defined in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Current project dependencies:
- **Runtime:** `pandas==3.0.6`, `openpyxl==3.1.5`
- **Development / Testing:** `pytest==9.1.1`

#### 3. Run Tests

Execute the complete test suite using pytest:

```bash
pytest -v
```

Or directly via the virtual environment binary without activating:

```bash
./.venv/bin/pytest -v
```

---

## CLI Usage

The command-line interface can be run directly using the Python interpreter:

```bash
python src/csv_cleaner/cli.py --help
```
*(or `PYTHONPATH=src python -m csv_cleaner --help`)*

### Supported Options

| Option | Flag Alias | Description | Required? |
| :--- | :--- | :--- | :--- |
| `-i, --input PATH` | | Path to the input CSV or XLSX file. | Yes |
| `-o, --output PATH` | | Path for the cleaned output CSV or XLSX file. | Yes |
| `-r, --report PATH` | | Optional path to save the JSON processing audit report. | No |
| `--overwrite` | | Allow overwriting existing output or report files. | No (default: False) |
| `--numeric-cols COL [COL ...]` | `--numeric-columns` | Column names to validate as numeric values. | No |
| `--date-cols COL [COL ...]` | `--date-columns` | Column names to validate as date values. | No |
| `--date-format FORMAT` | | Explicit strptime format required when date columns are specified (e.g. `'%Y-%m-%d'`). | Required if `--date-cols` passed |
| `-h, --help` | | Show usage documentation and exit. | No |

---

## Realistic End-to-End Example

The repository includes a synthetic raw dataset at `examples/input/sample_data.csv`:

```csv
 Customer ID ,Full-Name, Signup-Date ,ACCOUNT BALANCE 
101,Alice Smith,2025-01-15,250.75
102,Bob Jones,2025-02-20,unknown_balance
103,Charlie Taylor,,150.00
101,Alice Smith,2025-01-15,250.75
104,Diana Prince,2025-03-32,95.50
```

Notice:
- Inconsistent headers (` Customer ID `, `Full-Name`, ` Signup-Date `, `ACCOUNT BALANCE `).
- Row 1 and Row 4 are exact duplicates.
- Row 3 has a missing `signup_date`.
- Row 2 has an invalid balance string (`"unknown_balance"`).
- Row 5 has an invalid calendar date (`"2025-03-32"`).

### Run Command

```bash
python src/csv_cleaner/cli.py \
  -i examples/input/sample_data.csv \
  -o examples/output/sample_cleaned.csv \
  -r examples/output/sample_report.json \
  --numeric-cols account_balance \
  --date-cols signup_date \
  --date-format "%Y-%m-%d" \
  --overwrite
```

### Terminal Output

```
✓ Cleaning completed successfully:
  Input:               examples/input/sample_data.csv
  Output:              examples/output/sample_cleaned.csv
  Report:              examples/output/sample_report.json
  Original rows:       5
  Final rows:          4
  Duplicates removed:  1
  Total missing cells: 1
  Suspicious values:   2
  Warnings:
    - Removed 1 exact duplicate row(s).
    - Found 1 suspicious non-numeric value(s) in column 'account_balance'.
    - Found 1 unparseable date value(s) in column 'signup_date' with format '%Y-%m-%d'.
```

### Resulting Cleaned CSV (`examples/output/sample_cleaned.csv`)

```csv
customer_id,full_name,signup_date,account_balance
101,Alice Smith,2025-01-15,250.75
102,Bob Jones,2025-02-20,unknown_balance
103,Charlie Taylor,,150.00
104,Diana Prince,2025-03-32,95.50
```

---

## Explanation of the Generated JSON Report

When `--report <PATH>` is passed, a machine-readable JSON document is produced:

```json
{
  "status": "warning",
  "input_file": "examples/input/sample_data.csv",
  "output_file": "examples/output/sample_cleaned.csv",
  "original_row_count": 5,
  "final_row_count": 4,
  "duplicate_rows_removed": 1,
  "row_counts": {
    "original": 5,
    "final": 4,
    "duplicates_removed": 1
  },
  "missing_values": {
    "total_missing_cells": 1,
    "columns": {
      "signup_date": {
        "count": 1,
        "percentage": 25.0
      }
    }
  },
  "suspicious_data": {
    "numeric_issues": {
      "account_balance": [
        {
          "row_index": 1,
          "original_value": "unknown_balance"
        }
      ]
    },
    "date_issues": {
      "signup_date": [
        {
          "row_index": 4,
          "original_value": "2025-03-32"
        }
      ]
    }
  },
  "warnings": [
    "Removed 1 exact duplicate row(s).",
    "Found 1 suspicious non-numeric value(s) in column 'account_balance'.",
    "Found 1 unparseable date value(s) in column 'signup_date' with format '%Y-%m-%d'."
  ]
}
```

### Key Report Fields

- **`status`**: `"success"` if no warnings or issues occurred, or `"warning"` if anomalies/duplicates were found.
- **`input_file` / `output_file`**: Absolute or relative paths of the input and cleaned files.
- **`row_counts`**: Breakdown of original row count, final row count, and number of dropped duplicate rows.
- **`missing_values`**:
  - `total_missing_cells`: Aggregate count of empty/null values across the dataset.
  - `columns`: Map of affected columns with individual missing count and percentage of total rows.
- **`suspicious_data`**:
  - `numeric_issues`: Non-empty values in numeric columns that could not be parsed as numbers, identified by row index and raw original value.
  - `date_issues`: Non-empty values in date columns that failed to parse with the supplied format.
- **`warnings`**: Human-readable summaries of operations performed and anomalies found.

---

## Known Limitations

1. **In-Memory Ingestion**: Files are loaded entirely into memory using pandas DataFrames. Datasets exceeding available RAM may require chunked processing, which is not currently implemented.
2. **Exact Duplicate Removal Only**: Deduplication drops only rows where every single column is identical. Partial deduplication (e.g. matching only by `customer_id`) or fuzzy matching is not performed.
3. **Strict Date Parsing**: The tool enforces explicit date formats (e.g. `"%Y-%m-%d"`). It deliberately avoids heuristic guessing for ambiguous dates like `03/04/2025` to maintain data integrity.
4. **Excel Sheet Selection**: For `.xlsx` files, only the active first worksheet is ingested. Multi-sheet workbook processing is not supported.
5. **No Data Imputation**: Missing or invalid values are reported with row indices and original values, but are intentionally not automatically imputed or dropped.

---

## Project Structure

```text
csv-excel-data-cleaner/
├── .gitignore               # Git ignore rules for Python, virtual environments, caches
├── pyproject.toml           # Project and test configuration (pytest pythonpath = ["src"])
├── requirements.txt         # Pinned runtime and testing dependencies
├── README.md                # Project documentation and CLI usage guide
├── examples/
│   ├── input/
│   │   ├── .gitkeep         # Directory marker
│   │   └── sample_data.csv  # Synthetic test dataset
│   └── output/
│       └── .gitkeep         # Directory marker (generated files ignored)
├── src/
│   └── csv_cleaner/         # Core application package
│       ├── __init__.py      # Package entry and version
│       ├── __main__.py      # Module execution entry point
│       ├── reader.py        # File ingestion (CSV / XLSX)
│       ├── cleaner.py       # Column standardization and exact duplicate removal
│       ├── validator.py     # Missing value analysis and suspicious data detection
│       ├── reporter.py      # Cleaned file export and JSON report generation
│       └── cli.py           # Command-line interface and pipeline orchestration
└── tests/                   # Pytest test suite
    ├── test_reader.py       # Unit tests for reader module
    ├── test_cleaner.py      # Unit tests for cleaner module
    ├── test_validator.py    # Unit tests for validator module
    ├── test_reporter.py     # Unit tests for file export and report generation
    └── test_cli.py          # Unit and end-to-end tests for CLI
```
