"""Tests for csv_cleaner.validator module."""

import numpy as np
import pandas as pd
import pytest

from csv_cleaner.validator import (
    ColumnMissingStats,
    MissingValueAnalysis,
    SuspiciousValue,
    SuspiciousValueAnalysis,
    analyze_missing_values,
    analyze_suspicious_values,
    find_invalid_date_values,
    find_invalid_numeric_values,
)


def test_validator_module_imports() -> None:
    """Verify that validator module can be imported and exports expected objects."""
    import csv_cleaner.validator

    assert hasattr(csv_cleaner.validator, "analyze_missing_values")
    assert hasattr(csv_cleaner.validator, "find_invalid_numeric_values")
    assert hasattr(csv_cleaner.validator, "find_invalid_date_values")
    assert hasattr(csv_cleaner.validator, "analyze_suspicious_values")


def test_columns_with_no_missing_values() -> None:
    """Verify analysis on a DataFrame with complete data and no missing values."""
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "score": [10.5, 20.0, 30.2],
        }
    )

    analysis = analyze_missing_values(df)

    assert isinstance(analysis, MissingValueAnalysis)
    assert analysis.total_missing_cells == 0
    assert analysis.affected_columns == {}
    assert len(analysis.columns) == 0


def test_columns_with_missing_values_and_counts_percentages() -> None:
    """Verify detection of missing values and accuracy of counts and percentages."""
    df = pd.DataFrame(
        {
            "col_a": [1, None, 3, None],  # 2 missing (50%)
            "col_b": ["x", "y", "z", None],  # 1 missing (25%)
            "col_c": [10, 20, 30, 40],  # 0 missing
            "col_d": ["", "text", "", "ok"],  # empty strings are not nulls (0 missing)
        }
    )

    analysis = analyze_missing_values(df)

    # Affected columns
    assert "col_a" in analysis.affected_columns
    assert "col_b" in analysis.affected_columns
    assert "col_c" not in analysis.affected_columns
    assert "col_d" not in analysis.affected_columns  # empty string not treated as null

    assert analysis.columns["col_a"].count == 2
    assert analysis.columns["col_a"].percentage == 50.0

    assert analysis.columns["col_b"].count == 1
    assert analysis.columns["col_b"].percentage == 25.0


def test_total_missing_cell_count() -> None:
    """Verify calculation of total missing cells across all affected columns."""
    df = pd.DataFrame(
        {
            "x": [np.nan, 2.0, np.nan],
            "y": ["a", None, None],
            "z": [1, 2, 3],
        }
    )

    analysis = analyze_missing_values(df)
    assert analysis.total_missing_cells == 4


def test_numeric_columns_containing_valid_and_invalid_values() -> None:
    """Verify identification of non-empty values that cannot be parsed as numeric."""
    df = pd.DataFrame(
        {
            "amount": [10, "20.5", "-30", "invalid_text", None, "N/A", True],
        },
        index=[10, 20, 30, 40, 50, 60, 70],
    )

    issues = find_invalid_numeric_values(df, "amount")

    assert len(issues) == 3
    # Check problematic row indexes and original values
    assert issues[0] == SuspiciousValue(row_index=40, original_value="invalid_text")
    assert issues[1] == SuspiciousValue(row_index=60, original_value="N/A")
    assert issues[2] == SuspiciousValue(row_index=70, original_value=True)


def test_date_columns_with_valid_explicit_format() -> None:
    """Verify parsing when all non-empty dates match the explicit date format."""
    df = pd.DataFrame(
        {
            "join_date": ["2025-01-15", "2025-02-28", None, ""],
        }
    )

    issues = find_invalid_date_values(df, "join_date", date_format="%Y-%m-%d")
    assert issues == []


def test_invalid_dates() -> None:
    """Verify identification of dates that do not match the explicit format or are invalid."""
    df = pd.DataFrame(
        {
            "event_date": [
                "2025-01-15",  # valid
                "2025-02-30",  # invalid day for February
                "not-a-date",  # garbage
                "2025-13-01",  # invalid month
            ]
        },
        index=["r1", "r2", "r3", "r4"],
    )

    issues = find_invalid_date_values(df, "event_date", date_format="%Y-%m-%d")

    assert len(issues) == 3
    assert issues[0] == SuspiciousValue(row_index="r2", original_value="2025-02-30")
    assert issues[1] == SuspiciousValue(row_index="r3", original_value="not-a-date")
    assert issues[2] == SuspiciousValue(row_index="r4", original_value="2025-13-01")


def test_ambiguous_date_values_without_explicit_format() -> None:
    """Verify that ambiguous dates without an explicit format raise a clear error."""
    df = pd.DataFrame({"ambiguous_date": ["03/04/2025"]})

    with pytest.raises(ValueError, match="explicit date format"):
        find_invalid_date_values(df, "ambiguous_date", date_format=None)

    with pytest.raises(ValueError, match="explicit date format"):
        find_invalid_date_values(df, "ambiguous_date", date_format="   ")

    # With format specified as %Y-%m-%d, 03/04/2025 cannot be parsed and is reported
    issues = find_invalid_date_values(df, "ambiguous_date", date_format="%Y-%m-%d")
    assert len(issues) == 1
    assert issues[0].original_value == "03/04/2025"


def test_empty_dataframes_and_empty_columns() -> None:
    """Verify validator behavior on empty DataFrames and columns with 100% missing values."""
    # Completely empty DataFrame
    df_empty = pd.DataFrame()
    analysis_empty = analyze_missing_values(df_empty)
    assert analysis_empty.total_missing_cells == 0
    assert analysis_empty.affected_columns == {}

    # DataFrame with columns but 0 rows
    df_empty_cols = pd.DataFrame(columns=["num_col", "date_col"])
    analysis_empty_cols = analyze_missing_values(df_empty_cols)
    assert analysis_empty_cols.total_missing_cells == 0
    assert analysis_empty_cols.affected_columns == {}

    num_empty = find_invalid_numeric_values(df_empty_cols, "num_col")
    assert num_empty == []

    date_empty = find_invalid_date_values(df_empty_cols, "date_col", date_format="%Y-%m-%d")
    assert date_empty == []

    # Column with 100% missing values
    df_all_null = pd.DataFrame({"all_null": [None, np.nan, None]})
    analysis_null = analyze_missing_values(df_all_null)
    assert analysis_null.total_missing_cells == 3
    assert analysis_null.columns["all_null"].count == 3
    assert analysis_null.columns["all_null"].percentage == 100.0


def test_original_dataframe_remains_unchanged() -> None:
    """Verify that validator functions do not modify the input DataFrame."""
    df = pd.DataFrame(
        {
            "num": [1, "two", 3],
            "dt": ["2025-01-01", "invalid", None],
        }
    )
    original_values = df.values.tolist()
    original_cols = list(df.columns)
    original_dtypes = list(df.dtypes)

    _ = analyze_missing_values(df)
    _ = find_invalid_numeric_values(df, "num")
    _ = find_invalid_date_values(df, "dt", date_format="%Y-%m-%d")
    _ = analyze_suspicious_values(
        df, numeric_columns=["num"], date_columns={"dt": "%Y-%m-%d"}
    )

    assert df.values.tolist() == original_values
    assert list(df.columns) == original_cols
    assert list(df.dtypes) == original_dtypes


def test_nonexistent_column_raises_error() -> None:
    """Verify that referencing nonexistent columns raises ValueError."""
    df = pd.DataFrame({"existing": [1, 2]})

    with pytest.raises(ValueError, match="Column 'missing' not found"):
        find_invalid_numeric_values(df, "missing")

    with pytest.raises(ValueError, match="Column 'missing' not found"):
        find_invalid_date_values(df, "missing", date_format="%Y-%m-%d")
