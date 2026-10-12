"""Tests for csv_cleaner.reporter module."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from csv_cleaner.reporter import (
    SUPPORTED_EXPORT_EXTENSIONS,
    export_cleaned_file,
    export_file,
    generate_cleaning_report,
    save_report,
    save_report_to_json,
)
from csv_cleaner.validator import (
    ColumnMissingStats,
    MissingValueAnalysis,
    SuspiciousValue,
    SuspiciousValueAnalysis,
)


def test_reporter_module_imports() -> None:
    """Verify that reporter module can be imported and exports expected functions."""
    import csv_cleaner.reporter

    assert hasattr(csv_cleaner.reporter, "export_cleaned_file")
    assert hasattr(csv_cleaner.reporter, "export_file")
    assert hasattr(csv_cleaner.reporter, "generate_cleaning_report")
    assert hasattr(csv_cleaner.reporter, "save_report_to_json")
    assert hasattr(csv_cleaner.reporter, "save_report")
    assert hasattr(csv_cleaner.reporter, "SUPPORTED_EXPORT_EXTENSIONS")


def test_csv_export_and_reloading(tmp_path: Path) -> None:
    """Verify exporting a DataFrame to CSV and reloading it reproduces identical data."""
    df = pd.DataFrame(
        {
            "user_id": [1, 2, 3],
            "username": ["alex", "beth", "charlie"],
            "score": [95.5, 88.0, 72.3],
        }
    )
    out_file = tmp_path / "users.csv"

    saved_path = export_cleaned_file(df, out_file)
    assert saved_path.exists()

    reloaded_df = pd.read_csv(out_file)
    assert list(reloaded_df.columns) == ["user_id", "username", "score"]
    assert len(reloaded_df) == 3
    assert list(reloaded_df["username"]) == ["alex", "beth", "charlie"]


def test_xlsx_export_and_reloading(tmp_path: Path) -> None:
    """Verify exporting a DataFrame to XLSX via openpyxl and reloading it."""
    df = pd.DataFrame(
        {
            "product_id": [101, 102],
            "price": [19.99, 49.99],
        }
    )
    out_file = tmp_path / "products.xlsx"

    saved_path = export_file(df, out_file)
    assert saved_path.exists()

    reloaded_df = pd.read_excel(out_file, engine="openpyxl")
    assert list(reloaded_df.columns) == ["product_id", "price"]
    assert len(reloaded_df) == 2
    assert list(reloaded_df["price"]) == [19.99, 49.99]


def test_unicode_turkish_characters_in_csv(tmp_path: Path) -> None:
    """Verify UTF-8 encoding accurately preserves Turkish/Unicode characters."""
    df = pd.DataFrame(
        {
            "şehir_adı": ["İstanbul", "İzmir", "Eskişehir", "Diyarbakır"],
            "özel_açıklama": ["çağdaş", "ılık", "şekerli", "özgün"],
        }
    )
    out_file = tmp_path / "turkish.csv"

    export_cleaned_file(df, out_file)

    reloaded_df = pd.read_csv(out_file, encoding="utf-8")
    assert list(reloaded_df.columns) == ["şehir_adı", "özel_açıklama"]
    assert list(reloaded_df["şehir_adı"]) == ["İstanbul", "İzmir", "Eskişehir", "Diyarbakır"]
    assert list(reloaded_df["özel_açıklama"]) == ["çağdaş", "ılık", "şekerli", "özgün"]


def test_empty_dataframe_export(tmp_path: Path) -> None:
    """Verify exporting empty DataFrames preserves column headers and empty row count."""
    df = pd.DataFrame(columns=["id", "name", "status"])

    csv_out = tmp_path / "empty.csv"
    xlsx_out = tmp_path / "empty.xlsx"

    export_cleaned_file(df, csv_out)
    export_cleaned_file(df, xlsx_out)

    reloaded_csv = pd.read_csv(csv_out)
    assert list(reloaded_csv.columns) == ["id", "name", "status"]
    assert len(reloaded_csv) == 0

    reloaded_xlsx = pd.read_excel(xlsx_out, engine="openpyxl")
    assert list(reloaded_xlsx.columns) == ["id", "name", "status"]
    assert len(reloaded_xlsx) == 0


def test_unsupported_output_extensions(tmp_path: Path) -> None:
    """Verify ValueError is raised when an unsupported output extension is given."""
    df = pd.DataFrame({"col": [1, 2]})

    for ext in [".txt", ".json", ".parquet", ".tsv"]:
        out_file = tmp_path / f"test{ext}"
        with pytest.raises(ValueError, match="Unsupported output format"):
            export_cleaned_file(df, out_file)


def test_creating_missing_output_directory(tmp_path: Path) -> None:
    """Verify export automatically creates nested non-existent destination directories."""
    df = pd.DataFrame({"a": [1]})
    nested_out = tmp_path / "parent_dir" / "sub_dir" / "output.csv"

    assert not nested_out.parent.exists()
    export_cleaned_file(df, nested_out)

    assert nested_out.exists()
    assert nested_out.parent.is_dir()


def test_preventing_accidental_overwrite(tmp_path: Path) -> None:
    """Verify FileExistsError is raised when output file already exists without overwrite=True."""
    df = pd.DataFrame({"a": [1]})
    out_file = tmp_path / "existing.csv"
    out_file.write_text("pre-existing content", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        export_cleaned_file(df, out_file, overwrite=False)

    # Content must remain uncorrupted
    assert out_file.read_text(encoding="utf-8") == "pre-existing content"


def test_explicit_overwrite_permission(tmp_path: Path) -> None:
    """Verify file is successfully overwritten when overwrite=True is explicitly passed."""
    out_file = tmp_path / "overwrite_target.csv"
    out_file.write_text("old data", encoding="utf-8")

    new_df = pd.DataFrame({"updated": [100, 200]})
    export_cleaned_file(new_df, out_file, overwrite=True)

    reloaded = pd.read_csv(out_file)
    assert list(reloaded.columns) == ["updated"]
    assert list(reloaded["updated"]) == [100, 200]


def test_preventing_input_output_path_collisions(tmp_path: Path) -> None:
    """Verify ValueError is raised if output path resolves to the same file as input path."""
    source_file = tmp_path / "source.csv"
    source_file.write_text("a,b\n1,2\n", encoding="utf-8")

    df = pd.DataFrame({"a": [9], "b": [8]})

    # Exact same Path object
    with pytest.raises(ValueError, match="cannot be identical"):
        export_cleaned_file(df, output_path=source_file, input_path=source_file, overwrite=True)

    # Relative path vs absolute path resolving to same target
    with pytest.raises(ValueError, match="cannot be identical"):
        export_cleaned_file(
            df,
            output_path=source_file.resolve(),
            input_path=source_file,
            overwrite=True,
        )


def test_ensuring_original_dataframe_remains_unchanged(tmp_path: Path) -> None:
    """Verify that export does not mutate the input DataFrame."""
    df = pd.DataFrame({"col1": [10, 20], "col2": ["foo", "bar"]})
    original_values = df.values.tolist()
    original_cols = list(df.columns)

    out_file = tmp_path / "exported.csv"
    export_cleaned_file(df, out_file)

    assert df.values.tolist() == original_values
    assert list(df.columns) == original_cols


# ==================== Milestone 6 Tests ====================


def test_correct_report_structure_and_counts() -> None:
    """Verify the structured report contains the required keys and exact count values."""
    report = generate_cleaning_report(
        original_row_count=100,
        final_row_count=90,
        duplicate_rows_removed=10,
        input_file="raw.csv",
        output_file="cleaned.csv",
        warnings=["Dropped 10 duplicate rows."],
        status="success",
    )

    assert isinstance(report, dict)
    assert report["status"] == "success"
    assert report["original_row_count"] == 100
    assert report["final_row_count"] == 90
    assert report["duplicate_rows_removed"] == 10
    assert report["row_counts"]["original"] == 100
    assert report["row_counts"]["final"] == 90
    assert report["row_counts"]["duplicates_removed"] == 10
    assert report["input_file"] == "raw.csv"
    assert report["output_file"] == "cleaned.csv"
    assert report["warnings"] == ["Dropped 10 duplicate rows."]


def test_missing_value_statistics() -> None:
    """Verify report integrates missing value statistics from MissingValueAnalysis."""
    missing_analysis = MissingValueAnalysis(
        total_missing_cells=7,
        columns={
            "age": ColumnMissingStats(count=5, percentage=5.0),
            "email": ColumnMissingStats(count=2, percentage=2.0),
        },
    )

    report = generate_cleaning_report(missing_analysis=missing_analysis)

    assert report["missing_values"] is not None
    assert report["missing_values"]["total_missing_cells"] == 7
    assert report["missing_values"]["columns"]["age"] == {"count": 5, "percentage": 5.0}
    assert report["missing_values"]["columns"]["email"] == {"count": 2, "percentage": 2.0}


def test_optional_input_output_filenames() -> None:
    """Verify input and output filenames are included when provided and None when omitted."""
    report_with_files = generate_cleaning_report(
        input_file=Path("data/raw.csv"), output_file=Path("data/clean.xlsx")
    )
    assert report_with_files["input_file"] == "data/raw.csv"
    assert report_with_files["output_file"] == "data/clean.xlsx"

    report_without_files = generate_cleaning_report()
    assert report_without_files["input_file"] is None
    assert report_without_files["output_file"] is None


def test_suspicious_data_findings() -> None:
    """Verify suspicious numeric and date value analysis findings are integrated into report."""
    suspicious_analysis = SuspiciousValueAnalysis(
        numeric_issues={
            "price": [SuspiciousValue(row_index=12, original_value="free")],
        },
        date_issues={
            "signup_date": [SuspiciousValue(row_index=45, original_value="2025-02-30")],
        },
    )

    report = generate_cleaning_report(suspicious_analysis=suspicious_analysis)

    assert report["suspicious_data"] is not None
    assert "price" in report["suspicious_data"]["numeric_issues"]
    assert report["suspicious_data"]["numeric_issues"]["price"][0] == {
        "row_index": 12,
        "original_value": "free",
    }
    assert "signup_date" in report["suspicious_data"]["date_issues"]
    assert report["suspicious_data"]["date_issues"]["signup_date"][0] == {
        "row_index": 45,
        "original_value": "2025-02-30",
    }


def test_unavailable_statistics_versus_zero_values() -> None:
    """Verify report clearly distinguishes unavailable stats (None) from genuine 0 values."""
    # Unavailable statistics
    report_unavailable = generate_cleaning_report(
        original_row_count=None,
        duplicate_rows_removed=None,
        missing_analysis=None,
        suspicious_analysis=None,
    )
    assert report_unavailable["original_row_count"] is None
    assert report_unavailable["duplicate_rows_removed"] is None
    assert report_unavailable["missing_values"] is None
    assert report_unavailable["suspicious_data"] is None

    # Genuine zero values
    zero_missing = MissingValueAnalysis(total_missing_cells=0, columns={})
    zero_suspicious = SuspiciousValueAnalysis(numeric_issues={}, date_issues={})
    report_zeros = generate_cleaning_report(
        original_row_count=50,
        final_row_count=50,
        duplicate_rows_removed=0,
        missing_analysis=zero_missing,
        suspicious_analysis=zero_suspicious,
    )
    assert report_zeros["duplicate_rows_removed"] == 0
    assert report_zeros["missing_values"] == {"total_missing_cells": 0, "columns": {}}
    assert report_zeros["suspicious_data"] == {"numeric_issues": {}, "date_issues": {}}


def test_json_serialization_and_readable_output(tmp_path: Path) -> None:
    """Verify report saves to readable UTF-8 JSON and reloads with accurate structure."""
    report = generate_cleaning_report(
        original_row_count=100,
        final_row_count=98,
        duplicate_rows_removed=2,
        input_file="input.csv",
        output_file="output.csv",
        warnings=["Türkçe karakterler doğrulandı."],
    )
    report_path = tmp_path / "report.json"

    saved_path = save_report_to_json(report, report_path, indent=2)
    assert saved_path.exists()

    raw_text = report_path.read_text(encoding="utf-8")
    assert "Türkçe karakterler doğrulandı." in raw_text
    assert "  \"original_row_count\": 100" in raw_text

    loaded = json.loads(raw_text)
    assert loaded["original_row_count"] == 100
    assert loaded["warnings"] == ["Türkçe karakterler doğrulandı."]


def test_creating_missing_report_parent_directory(tmp_path: Path) -> None:
    """Verify save_report creates missing nested directories."""
    nested_path = tmp_path / "audit" / "logs" / "cleaning_report.json"
    assert not nested_path.parent.exists()

    report = generate_cleaning_report(original_row_count=10)
    saved_path = save_report(report, nested_path)

    assert saved_path.exists()
    assert nested_path.parent.is_dir()


def test_preventing_accidental_report_overwrite(tmp_path: Path) -> None:
    """Verify FileExistsError is raised when report file exists without overwrite=True."""
    report_file = tmp_path / "existing_report.json"
    report_file.write_text('{"initial": true}', encoding="utf-8")

    report = generate_cleaning_report(original_row_count=5)

    with pytest.raises(FileExistsError, match="already exists"):
        save_report_to_json(report, report_file, overwrite=False)

    assert report_file.read_text(encoding="utf-8") == '{"initial": true}'


def test_explicit_report_overwrite_permission(tmp_path: Path) -> None:
    """Verify report file is updated when overwrite=True is explicitly supplied."""
    report_file = tmp_path / "overwrite_report.json"
    report_file.write_text('{"initial": true}', encoding="utf-8")

    report = generate_cleaning_report(original_row_count=50)
    save_report_to_json(report, report_file, overwrite=True)

    loaded = json.loads(report_file.read_text(encoding="utf-8"))
    assert loaded["original_row_count"] == 50


def test_handling_pandas_numpy_scalar_values(tmp_path: Path) -> None:
    """Verify pandas and NumPy scalars are serialized without TypeError."""
    report = {
        "np_int": np.int64(42),
        "np_float": np.float64(3.1415),
        "np_bool": np.bool_(True),
        "np_array": np.array([1, 2, 3]),
        "pd_timestamp": pd.Timestamp("2026-10-12 12:00:00"),
        "pd_na": pd.NA,
        "np_nan": np.nan,
    }
    report_path = tmp_path / "scalars_report.json"

    saved_path = save_report_to_json(report, report_path)
    assert saved_path.exists()

    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["np_int"] == 42
    assert pytest.approx(loaded["np_float"]) == 3.1415
    assert loaded["np_bool"] is True
    assert loaded["np_array"] == [1, 2, 3]
    assert loaded["pd_timestamp"] == "2026-10-12T12:00:00"
    assert loaded["pd_na"] is None
    assert loaded["np_nan"] is None


def test_ensuring_report_inputs_not_mutated() -> None:
    """Verify input arguments (lists, dicts, analysis objects) are not modified."""
    warnings_list = ["warning 1", "warning 2"]
    missing_dict = {"total_missing_cells": 1, "columns": {"c": {"count": 1, "percentage": 10.0}}}

    report = generate_cleaning_report(
        warnings=warnings_list,
        missing_analysis=missing_dict,
    )

    assert warnings_list == ["warning 1", "warning 2"]
    assert missing_dict == {"total_missing_cells": 1, "columns": {"c": {"count": 1, "percentage": 10.0}}}

    # Mutating returned report must not alter original lists
    report["warnings"].append("new warning")
    assert len(warnings_list) == 2


def test_invalid_report_data_and_writing_errors(tmp_path: Path) -> None:
    """Verify validation raises clear ValueErrors on invalid report data."""
    # Negative row counts
    with pytest.raises(ValueError, match="non-negative integer"):
        generate_cleaning_report(original_row_count=-1)

    with pytest.raises(ValueError, match="non-negative integer"):
        generate_cleaning_report(final_row_count=-1)

    with pytest.raises(ValueError, match="non-negative integer"):
        generate_cleaning_report(duplicate_rows_removed=-5)

    # final_row_count > original_row_count
    with pytest.raises(ValueError, match="cannot exceed"):
        generate_cleaning_report(original_row_count=10, final_row_count=20)

    # Invalid report structure for saving
    with pytest.raises(ValueError, match="must be a dictionary"):
        save_report_to_json("not a dictionary", tmp_path / "bad.json")  # type: ignore

    # Non-json extension
    with pytest.raises(ValueError, match="Expected '.json'"):
        save_report_to_json({}, tmp_path / "bad.txt")
