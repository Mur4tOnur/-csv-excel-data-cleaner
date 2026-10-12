"""Data validation module.

This module provides focused functions for detecting missing values and
identifying suspicious non-numeric or unparseable date values in pandas DataFrames.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence
import pandas as pd


@dataclass(frozen=True)
class ColumnMissingStats:
    """Missing value statistics for an individual column.

    Attributes
    ----------
    count : int
        The total count of missing/null values in this column.
    percentage : float
        The percentage of rows in this column that are missing (0.0 to 100.0).
    """

    count: int
    percentage: float


@dataclass(frozen=True)
class MissingValueAnalysis:
    """Overall summary of missing values across a DataFrame.

    Attributes
    ----------
    total_missing_cells : int
        The total count of all missing cells across the entire DataFrame.
    columns : dict[str, ColumnMissingStats]
        A mapping of affected column names to their missing value statistics.
    """

    total_missing_cells: int
    columns: dict[str, ColumnMissingStats]

    @property
    def affected_columns(self) -> dict[str, ColumnMissingStats]:
        """Alias for affected columns mapping."""
        return self.columns


@dataclass(frozen=True)
class SuspiciousValue:
    """Problematic value identified in a column.

    Attributes
    ----------
    row_index : Any
        The DataFrame index label of the row containing the problematic value.
    original_value : Any
        The original, unparsed value as it appeared in the DataFrame.
    """

    row_index: Any
    original_value: Any


@dataclass(frozen=True)
class SuspiciousValueAnalysis:
    """Summary of suspicious numeric and date values across specified columns.

    Attributes
    ----------
    numeric_issues : dict[str, list[SuspiciousValue]]
        Mapping of numeric column names to list of suspicious values found.
    date_issues : dict[str, list[SuspiciousValue]]
        Mapping of date column names to list of suspicious values found.
    """

    numeric_issues: dict[str, list[SuspiciousValue]]
    date_issues: dict[str, list[SuspiciousValue]]


def analyze_missing_values(df: pd.DataFrame) -> MissingValueAnalysis:
    """Analyze missing values in a DataFrame.

    Detects actual null values (e.g. None, NaN, pd.NA). Ordinary empty strings
    are not treated as missing. Reports statistics for all affected columns
    where missing values are present.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to inspect.

    Returns
    -------
    MissingValueAnalysis
        Structured result containing total missing cells and per-column stats
        for affected columns.
    """
    if df.empty or len(df.columns) == 0:
        return MissingValueAnalysis(total_missing_cells=0, columns={})

    total_rows = len(df)
    affected: dict[str, ColumnMissingStats] = {}
    total_missing = 0

    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            total_missing += null_count
            pct = round((null_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            affected[str(col)] = ColumnMissingStats(count=null_count, percentage=pct)

    return MissingValueAnalysis(total_missing_cells=total_missing, columns=affected)


def find_invalid_numeric_values(df: pd.DataFrame, column: str) -> list[SuspiciousValue]:
    """Identify non-empty values in a column that cannot be parsed as numeric.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing the target column.
    column : str
        The column name to analyze.

    Returns
    -------
    list[SuspiciousValue]
        A list of SuspiciousValue records with row_index and original_value.

    Raises
    ------
    ValueError
        If the column is not found in the DataFrame.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")

    suspicious: list[SuspiciousValue] = []
    series = df[column]

    for idx, val in series.items():
        if pd.isna(val):
            continue
        if isinstance(val, bool):
            suspicious.append(SuspiciousValue(row_index=idx, original_value=val))
            continue
        if isinstance(val, (int, float)):
            continue
        val_str = str(val).strip()
        if not val_str:
            continue
        try:
            float(val_str)
        except (ValueError, TypeError):
            suspicious.append(SuspiciousValue(row_index=idx, original_value=val))

    return suspicious


def find_invalid_date_values(
    df: pd.DataFrame, column: str, date_format: str | None = None
) -> list[SuspiciousValue]:
    """Identify non-empty values in a column that cannot be parsed using an explicit date format.

    Ambiguous dates are never guessed; the caller must supply the expected format.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing the target column.
    column : str
        The column name to analyze.
    date_format : str or None
        Explicit strptime format string (e.g. '%Y-%m-%d'). Cannot be empty or None.

    Returns
    -------
    list[SuspiciousValue]
        A list of SuspiciousValue records with row_index and original_value.

    Raises
    ------
    ValueError
        If date_format is None or empty, or if column is not found in DataFrame.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")

    if date_format is None or not str(date_format).strip():
        raise ValueError(
            f"An explicit date format must be supplied for column '{column}' "
            "(e.g. '%Y-%m-%d'). Silent date format inference is not permitted."
        )

    suspicious: list[SuspiciousValue] = []
    series = df[column]

    for idx, val in series.items():
        if pd.isna(val):
            continue
        if isinstance(val, (datetime, date)):
            continue
        val_str = str(val).strip()
        if not val_str:
            continue
        try:
            datetime.strptime(val_str, date_format)
        except (ValueError, TypeError):
            suspicious.append(SuspiciousValue(row_index=idx, original_value=val))

    return suspicious


def analyze_suspicious_values(
    df: pd.DataFrame,
    numeric_columns: Sequence[str] | None = None,
    date_columns: Mapping[str, str] | None = None,
) -> SuspiciousValueAnalysis:
    """Analyze multiple designated numeric and date columns for suspicious values.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to inspect.
    numeric_columns : Sequence[str] or None
        List of column names to validate as numeric.
    date_columns : Mapping[str, str] or None
        Mapping of column names to required explicit strptime date format strings.

    Returns
    -------
    SuspiciousValueAnalysis
        Structured result containing suspicious value records grouped by column.
    """
    numeric_issues: dict[str, list[SuspiciousValue]] = {}
    date_issues: dict[str, list[SuspiciousValue]] = {}

    if numeric_columns:
        for num_col in numeric_columns:
            issues = find_invalid_numeric_values(df, num_col)
            if issues:
                numeric_issues[num_col] = issues

    if date_columns:
        for dt_col, fmt in date_columns.items():
            issues = find_invalid_date_values(df, dt_col, date_format=fmt)
            if issues:
                date_issues[dt_col] = issues

    return SuspiciousValueAnalysis(numeric_issues=numeric_issues, date_issues=date_issues)
