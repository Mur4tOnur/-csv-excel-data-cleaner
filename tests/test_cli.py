"""Tests for csv_cleaner.cli module."""

import json
from pathlib import Path

import pandas as pd
import pytest

from csv_cleaner.cli import build_parser, main, run_pipeline


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify --help outputs usage information and exits with code 0."""
    exit_code = main(["--help"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower() or "csv-cleaner" in captured.out
    assert "--input" in captured.out
    assert "--output" in captured.out
    assert "--report" in captured.out
    assert "--overwrite" in captured.out
    assert "--numeric-cols" in captured.out
    assert "--date-cols" in captured.out
    assert "--date-format" in captured.out


def test_cli_successful_csv_processing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify end-to-end CLI execution on CSV file produces cleaned output and report."""
    in_csv = tmp_path / "raw.csv"
    in_csv.write_text(
        "  User ID  ,FULL NAME ,Amount \n"
        "1,Alice,100.5\n"
        "2,Bob,250.0\n"
        "1,Alice,100.5\n",  # duplicate row
        encoding="utf-8",
    )

    out_csv = tmp_path / "cleaned.csv"
    rep_json = tmp_path / "report.json"

    exit_code = main(["-i", str(in_csv), "-o", str(out_csv), "-r", str(rep_json)])
    assert exit_code == 0

    # Verify stdout summary
    captured = capsys.readouterr()
    assert "Cleaning completed successfully" in captured.out
    assert "Original rows:       3" in captured.out
    assert "Final rows:          2" in captured.out
    assert "Duplicates removed:  1" in captured.out

    # Verify cleaned CSV
    assert out_csv.exists()
    cleaned_df = pd.read_csv(out_csv)
    assert list(cleaned_df.columns) == ["user_id", "full_name", "amount"]
    assert len(cleaned_df) == 2

    # Verify report JSON
    assert rep_json.exists()
    report = json.loads(rep_json.read_text(encoding="utf-8"))
    assert report["original_row_count"] == 3
    assert report["final_row_count"] == 2
    assert report["duplicate_rows_removed"] == 1


def test_cli_successful_xlsx_processing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify end-to-end CLI execution on XLSX file produces cleaned XLSX and report."""
    in_xlsx = tmp_path / "raw.xlsx"
    pd.DataFrame(
        {
            "Product-Code": [101, 102, 101],
            "Price": [19.99, 29.99, 19.99],
        }
    ).to_excel(in_xlsx, index=False, engine="openpyxl")

    out_xlsx = tmp_path / "cleaned.xlsx"
    rep_json = tmp_path / "report.json"

    exit_code = main(["-i", str(in_xlsx), "-o", str(out_xlsx), "-r", str(rep_json)])
    assert exit_code == 0

    assert out_xlsx.exists()
    cleaned_df = pd.read_excel(out_xlsx, engine="openpyxl")
    assert list(cleaned_df.columns) == ["product_code", "price"]
    assert len(cleaned_df) == 2

    report = json.loads(rep_json.read_text(encoding="utf-8"))
    assert report["duplicate_rows_removed"] == 1


def test_cli_missing_value_reporting(tmp_path: Path) -> None:
    """Verify missing values are accurately analyzed and reported via CLI."""
    in_csv = tmp_path / "missing.csv"
    in_csv.write_text("a,b,c\n1,,10\n,y,20\n3,,30\n", encoding="utf-8")

    out_csv = tmp_path / "out.csv"
    rep_json = tmp_path / "report.json"

    exit_code = main(["-i", str(in_csv), "-o", str(out_csv), "-r", str(rep_json)])
    assert exit_code == 0

    report = json.loads(rep_json.read_text(encoding="utf-8"))
    assert report["missing_values"]["total_missing_cells"] == 3
    assert report["missing_values"]["columns"]["a"]["count"] == 1
    assert report["missing_values"]["columns"]["b"]["count"] == 2


def test_cli_optional_json_report(tmp_path: Path) -> None:
    """Verify CLI works cleanly when optional -r/--report is omitted."""
    in_csv = tmp_path / "sample.csv"
    in_csv.write_text("id,val\n1,10\n", encoding="utf-8")
    out_csv = tmp_path / "out.csv"

    exit_code = main(["-i", str(in_csv), "-o", str(out_csv)])
    assert exit_code == 0
    assert out_csv.exists()


def test_cli_numeric_and_date_validation_options(tmp_path: Path) -> None:
    """Verify --numeric-cols, --date-cols, and --date-format options."""
    in_csv = tmp_path / "validation_test.csv"
    in_csv.write_text(
        "id,amount,event_date\n"
        "1,100,2025-01-15\n"
        "2,bad_num,2025-02-30\n"  # bad number & invalid February date
        "3,300,2025-03-01\n",
        encoding="utf-8",
    )

    out_csv = tmp_path / "out.csv"
    rep_json = tmp_path / "report.json"

    exit_code = main(
        [
            "-i",
            str(in_csv),
            "-o",
            str(out_csv),
            "-r",
            str(rep_json),
            "--numeric-cols",
            "amount",
            "--date-cols",
            "event_date",
            "--date-format",
            "%Y-%m-%d",
        ]
    )
    assert exit_code == 0

    report = json.loads(rep_json.read_text(encoding="utf-8"))
    assert report["suspicious_data"] is not None

    numeric_issues = report["suspicious_data"]["numeric_issues"]["amount"]
    assert len(numeric_issues) == 1
    assert numeric_issues[0]["original_value"] == "bad_num"

    date_issues = report["suspicious_data"]["date_issues"]["event_date"]
    assert len(date_issues) == 1
    assert date_issues[0]["original_value"] == "2025-02-30"


def test_cli_invalid_input_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify non-existent input file returns code 1 and prints clear error to stderr."""
    missing_in = tmp_path / "does_not_exist.csv"
    out_csv = tmp_path / "out.csv"

    exit_code = main(["-i", str(missing_in), "-o", str(out_csv)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: File not found" in captured.err
    assert not out_csv.exists()


def test_cli_unsupported_extensions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify unsupported input or output formats return code 1 with clear error."""
    bad_in = tmp_path / "data.txt"
    bad_in.write_text("hello", encoding="utf-8")
    out_csv = tmp_path / "out.csv"

    exit_code = main(["-i", str(bad_in), "-o", str(out_csv)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Unsupported" in captured.err

    # Bad output format
    good_in = tmp_path / "data.csv"
    good_in.write_text("a,b\n1,2\n", encoding="utf-8")
    bad_out = tmp_path / "out.parquet"

    exit_code = main(["-i", str(good_in), "-o", str(bad_out)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Unsupported output format" in captured.err


def test_cli_missing_date_format_when_date_cols_specified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify specifying --date-cols without --date-format returns code 1 with clear error."""
    in_csv = tmp_path / "data.csv"
    in_csv.write_text("dt\n2025-01-01\n", encoding="utf-8")
    out_csv = tmp_path / "out.csv"

    exit_code = main(["-i", str(in_csv), "-o", str(out_csv), "--date-cols", "dt"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "--date-format must be provided" in captured.err


def test_cli_existing_output_without_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify existing output file without --overwrite returns code 1 and preserves existing file."""
    in_csv = tmp_path / "input.csv"
    in_csv.write_text("id\n1\n", encoding="utf-8")

    out_csv = tmp_path / "output.csv"
    out_csv.write_text("original content", encoding="utf-8")

    exit_code = main(["-i", str(in_csv), "-o", str(out_csv)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "already exists" in captured.err
    assert out_csv.read_text(encoding="utf-8") == "original content"

    # With --overwrite it succeeds
    exit_code_ow = main(["-i", str(in_csv), "-o", str(out_csv), "--overwrite"])
    assert exit_code_ow == 0
    assert "original content" not in out_csv.read_text(encoding="utf-8")


def test_cli_input_output_path_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify input and output paths resolving to the same file return code 1."""
    same_file = tmp_path / "data.csv"
    same_file.write_text("a,b\n1,2\n", encoding="utf-8")

    exit_code = main(["-i", str(same_file), "-o", str(same_file), "--overwrite"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "cannot be identical" in captured.err
    # File is intact
    assert same_file.read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_cli_missing_required_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify missing required input or output arguments return code 1."""
    exit_code_no_args = main([])
    assert exit_code_no_args == 1
    captured = capsys.readouterr()
    assert "Missing required input file" in captured.err

    exit_code_no_out = main(["-i", "input.csv"])
    assert exit_code_no_out == 1
    captured2 = capsys.readouterr()
    assert "Missing required output file" in captured2.err
