"""Reporting and export module for data cleaning runs.

This module provides functionality to safely export cleaned DataFrames to CSV
and XLSX files, and to generate and serialize comprehensive processing reports
as human-readable UTF-8 JSON documents.
"""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, Final, Sequence, Union

import numpy as np
import pandas as pd

from csv_cleaner.validator import MissingValueAnalysis, SuspiciousValueAnalysis

SUPPORTED_EXPORT_EXTENSIONS: Final[tuple[str, ...]] = (".csv", ".xlsx")


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert custom, pandas, and NumPy objects into JSON-serializable types."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _sanitize_for_json(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.integer, int)) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        if pd.isna(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_sanitize_for_json(v) for v in obj.tolist()]
    if pd.isna(obj):
        return None
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def export_cleaned_file(
    df: pd.DataFrame,
    output_path: Union[str, Path],
    input_path: Union[str, Path, None] = None,
    overwrite: bool = False,
) -> Path:
    """Export a pandas DataFrame to a CSV or XLSX file.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to export. The input DataFrame is never modified.
    output_path : str or pathlib.Path
        The destination file path (.csv or .xlsx).
    input_path : str or pathlib.Path, optional
        The original input file path. If provided, verifies that output_path does
        not resolve to the same file, preventing accidental destruction of source data.
    overwrite : bool, default False
        Whether to overwrite an existing output file. If False and the destination
        exists, an error is raised.

    Returns
    -------
    pathlib.Path
        The resolved Path of the successfully written file.

    Raises
    ------
    ValueError
        If the output extension is unsupported, or if output_path resolves to
        the same file as input_path.
    FileExistsError
        If output_path already exists and overwrite is False.
    OSError
        If the file cannot be written due to I/O or permissions errors.
    """
    out_p = Path(output_path)
    suffix = out_p.suffix.lower()

    if suffix not in SUPPORTED_EXPORT_EXTENSIONS:
        supported_str = ", ".join(SUPPORTED_EXPORT_EXTENSIONS)
        raise ValueError(
            f"Unsupported output format '{out_p.suffix}'. Supported formats are: {supported_str}"
        )

    # Prevent overwriting original input file
    if input_path is not None:
        in_resolved = Path(input_path).resolve()
        out_resolved = out_p.resolve()
        if in_resolved == out_resolved:
            raise ValueError(
                f"Output path cannot be identical to the original input file: '{output_path}'"
            )

    # Enforce explicit overwrite permission
    if out_p.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: '{output_path}'. Set overwrite=True to allow overwriting."
        )

    # Ensure parent directory exists
    try:
        out_p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Failed to create output directory '{out_p.parent}': {exc}") from exc

    # Export using appropriate engine and encoding
    try:
        if suffix == ".csv":
            df.to_csv(out_p, index=False, encoding="utf-8")
        else:  # .xlsx
            df.to_excel(out_p, index=False, engine="openpyxl")
    except Exception as exc:
        raise OSError(f"Failed to export file to '{output_path}': {exc}") from exc

    return out_p


# Convenience alias
export_file = export_cleaned_file


def generate_cleaning_report(
    original_row_count: Union[int, None] = None,
    final_row_count: Union[int, None] = None,
    duplicate_rows_removed: Union[int, None] = None,
    missing_analysis: Union[MissingValueAnalysis, dict[str, Any], None] = None,
    suspicious_analysis: Union[SuspiciousValueAnalysis, dict[str, Any], None] = None,
    input_file: Union[str, Path, None] = None,
    output_file: Union[str, Path, None] = None,
    warnings: Union[Sequence[str], None] = None,
    status: str = "success",
) -> dict[str, Any]:
    """Generate a structured processing report for a data cleaning run.

    Unavailable statistics remain None to clearly distinguish missing information
    from genuine zero values.

    Parameters
    ----------
    original_row_count : int or None, optional
        Total row count of the raw input dataset before cleaning.
    final_row_count : int or None, optional
        Row count of the cleaned dataset.
    duplicate_rows_removed : int or None, optional
        Count of exact duplicate rows dropped.
    missing_analysis : MissingValueAnalysis or dict or None, optional
        Structured missing-value statistics from validator.
    suspicious_analysis : SuspiciousValueAnalysis or dict or None, optional
        Structured suspicious numeric and date value analysis from validator.
    input_file : str or pathlib.Path or None, optional
        Original input file name or path.
    output_file : str or pathlib.Path or None, optional
        Cleaned export file name or path.
    warnings : Sequence[str] or None, optional
        List of operational warnings or alerts encountered during processing.
    status : str, default 'success'
        Overall processing outcome ('success', 'warning', or 'error').

    Returns
    -------
    dict[str, Any]
        A structured dictionary ready for JSON serialization.

    Raises
    ------
    ValueError
        If row counts are negative or final row count exceeds original row count.
    """
    if original_row_count is not None:
        if not isinstance(original_row_count, (int, np.integer)) or original_row_count < 0:
            raise ValueError(
                f"original_row_count must be a non-negative integer, got: {original_row_count}"
            )
        original_row_count = int(original_row_count)

    if final_row_count is not None:
        if not isinstance(final_row_count, (int, np.integer)) or final_row_count < 0:
            raise ValueError(
                f"final_row_count must be a non-negative integer, got: {final_row_count}"
            )
        final_row_count = int(final_row_count)

    if duplicate_rows_removed is not None:
        if not isinstance(duplicate_rows_removed, (int, np.integer)) or duplicate_rows_removed < 0:
            raise ValueError(
                f"duplicate_rows_removed must be a non-negative integer, got: {duplicate_rows_removed}"
            )
        duplicate_rows_removed = int(duplicate_rows_removed)

    if original_row_count is not None and final_row_count is not None:
        if final_row_count > original_row_count:
            raise ValueError(
                f"final_row_count ({final_row_count}) cannot exceed original_row_count ({original_row_count})"
            )

    missing_data: Union[dict[str, Any], None] = None
    if missing_analysis is not None:
        if hasattr(missing_analysis, "total_missing_cells") and hasattr(missing_analysis, "columns"):
            cols_summary: dict[str, dict[str, Any]] = {}
            for col_name, stats in missing_analysis.columns.items():
                if hasattr(stats, "count") and hasattr(stats, "percentage"):
                    cols_summary[str(col_name)] = {
                        "count": int(stats.count),
                        "percentage": float(stats.percentage),
                    }
                elif isinstance(stats, dict):
                    cols_summary[str(col_name)] = {
                        "count": int(stats.get("count", 0)),
                        "percentage": float(stats.get("percentage", 0.0)),
                    }
            missing_data = {
                "total_missing_cells": int(missing_analysis.total_missing_cells),
                "columns": cols_summary,
            }
        elif isinstance(missing_analysis, dict):
            missing_data = _sanitize_for_json(missing_analysis)

    suspicious_data: Union[dict[str, Any], None] = None
    if suspicious_analysis is not None:
        if hasattr(suspicious_analysis, "numeric_issues") and hasattr(suspicious_analysis, "date_issues"):
            num_issues: dict[str, list[dict[str, Any]]] = {}
            for col, issues in suspicious_analysis.numeric_issues.items():
                num_issues[str(col)] = [
                    {
                        "row_index": _sanitize_for_json(getattr(iss, "row_index", None)),
                        "original_value": _sanitize_for_json(getattr(iss, "original_value", None)),
                    }
                    if hasattr(iss, "row_index")
                    else _sanitize_for_json(iss)
                    for iss in issues
                ]

            dt_issues: dict[str, list[dict[str, Any]]] = {}
            for col, issues in suspicious_analysis.date_issues.items():
                dt_issues[str(col)] = [
                    {
                        "row_index": _sanitize_for_json(getattr(iss, "row_index", None)),
                        "original_value": _sanitize_for_json(getattr(iss, "original_value", None)),
                    }
                    if hasattr(iss, "row_index")
                    else _sanitize_for_json(iss)
                    for iss in issues
                ]

            suspicious_data = {
                "numeric_issues": num_issues,
                "date_issues": dt_issues,
            }
        elif isinstance(suspicious_analysis, dict):
            suspicious_data = _sanitize_for_json(suspicious_analysis)

    report: dict[str, Any] = {
        "status": str(status),
        "input_file": str(input_file) if input_file is not None else None,
        "output_file": str(output_file) if output_file is not None else None,
        "original_row_count": original_row_count,
        "final_row_count": final_row_count,
        "duplicate_rows_removed": duplicate_rows_removed,
        "row_counts": {
            "original": original_row_count,
            "final": final_row_count,
            "duplicates_removed": duplicate_rows_removed,
        },
        "missing_values": missing_data,
        "suspicious_data": suspicious_data,
        "warnings": [_sanitize_for_json(w) for w in warnings] if warnings is not None else [],
    }
    return report


def save_report_to_json(
    report: dict[str, Any],
    output_path: Union[str, Path],
    overwrite: bool = False,
    indent: int = 2,
) -> Path:
    """Save a cleaning report dictionary to a human-readable UTF-8 JSON file.

    Parameters
    ----------
    report : dict[str, Any]
        The structured report dictionary to serialize.
    output_path : str or pathlib.Path
        The destination JSON file path.
    overwrite : bool, default False
        Whether to overwrite an existing report file. If False and the destination
        exists, FileExistsError is raised.
    indent : int, default 2
        Indentation spaces for formatting.

    Returns
    -------
    pathlib.Path
        The resolved Path of the written report file.

    Raises
    ------
    ValueError
        If report is not a dictionary or output extension is not .json.
    FileExistsError
        If output file already exists and overwrite is False.
    OSError
        If file writing fails due to I/O or permissions issues.
    """
    if not isinstance(report, dict):
        raise ValueError(f"Report must be a dictionary, got: {type(report).__name__}")

    out_p = Path(output_path)
    if out_p.suffix.lower() != ".json":
        raise ValueError(
            f"Invalid report output format '{out_p.suffix}'. Expected '.json'."
        )

    if out_p.exists() and not overwrite:
        raise FileExistsError(
            f"Report file already exists: '{output_path}'. Set overwrite=True to allow overwriting."
        )

    try:
        out_p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Failed to create directory '{out_p.parent}': {exc}") from exc

    sanitized = _sanitize_for_json(report)

    try:
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=indent, ensure_ascii=False)
            f.write("\n")
    except Exception as exc:
        raise OSError(f"Failed to write report to '{output_path}': {exc}") from exc

    return out_p


# Convenience alias
save_report = save_report_to_json
