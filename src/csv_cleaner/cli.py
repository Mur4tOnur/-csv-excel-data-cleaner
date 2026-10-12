"""Command-line interface for CSV & Excel Data Cleaner.

This module provides the terminal interface for reading, cleaning,
validating, and exporting tabular datasets and generating audit reports.
"""

import argparse
from pathlib import Path
import sys
from typing import Any, Sequence, Union

# Ensure parent directory (src/) is in sys.path when invoked directly as a script
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from csv_cleaner.cleaner import remove_duplicate_rows, standardize_column_name, standardize_column_names
from csv_cleaner.reader import SUPPORTED_EXTENSIONS, read_file
from csv_cleaner.reporter import (
    SUPPORTED_EXPORT_EXTENSIONS,
    export_cleaned_file,
    generate_cleaning_report,
    save_report_to_json,
)
from csv_cleaner.validator import (
    SuspiciousValueAnalysis,
    analyze_missing_values,
    find_invalid_date_values,
    find_invalid_numeric_values,
)


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="csv-cleaner",
        description="CSV & Excel Data Cleaner: Standardize columns, remove duplicates, validate data, and export cleaned files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        metavar="PATH",
        help="Path to the input CSV or XLSX file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="PATH",
        help="Path for the cleaned output CSV or XLSX file.",
    )
    parser.add_argument(
        "-r",
        "--report",
        dest="report",
        metavar="PATH",
        default=None,
        help="Optional path to save the JSON processing audit report.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Allow overwriting existing output or report files.",
    )
    parser.add_argument(
        "--numeric-cols",
        "--numeric-columns",
        dest="numeric_cols",
        nargs="+",
        metavar="COL",
        default=None,
        help="Column names to validate as numeric values.",
    )
    parser.add_argument(
        "--date-cols",
        "--date-columns",
        dest="date_cols",
        nargs="+",
        metavar="COL",
        default=None,
        help="Column names to validate as date values.",
    )
    parser.add_argument(
        "--date-format",
        dest="date_format",
        metavar="FORMAT",
        default=None,
        help="Explicit strptime format required when date columns are specified (e.g. '%%Y-%%m-%%d').",
    )

    # Optional positional fallbacks if options are omitted
    parser.add_argument(
        "input_pos",
        nargs="?",
        metavar="INPUT",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "output_pos",
        nargs="?",
        metavar="OUTPUT",
        help=argparse.SUPPRESS,
    )

    return parser


def run_pipeline(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    report_path: Union[str, Path, None] = None,
    numeric_cols: Union[Sequence[str], None] = None,
    date_cols: Union[Sequence[str], None] = None,
    date_format: Union[str, None] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Execute the full data cleaning and validation pipeline.

    Parameters
    ----------
    input_path : str or pathlib.Path
        Path to source CSV/XLSX file.
    output_path : str or pathlib.Path
        Path for destination cleaned file.
    report_path : str or pathlib.Path or None, optional
        Optional path for destination JSON report file.
    numeric_cols : Sequence[str] or None, optional
        List of column names to validate as numeric.
    date_cols : Sequence[str] or None, optional
        List of column names to validate as dates.
    date_format : str or None, optional
        Required strptime format when date_cols is provided.
    overwrite : bool, default False
        Whether to permit overwriting destination files.

    Returns
    -------
    dict[str, Any]
        The structured processing report.

    Raises
    ------
    ValueError, FileNotFoundError, FileExistsError
        If path, format, or data validation fails.
    """
    in_p = Path(input_path)
    out_p = Path(output_path)
    rep_p = Path(report_path) if report_path is not None else None

    # Pre-flight option validation
    if date_cols and (date_format is None or not str(date_format).strip()):
        raise ValueError(
            "--date-format must be provided when date columns are specified via --date-cols (e.g. '%Y-%m-%d')."
        )

    # Validate output extension
    if out_p.suffix.lower() not in SUPPORTED_EXPORT_EXTENSIONS:
        supported_str = ", ".join(SUPPORTED_EXPORT_EXTENSIONS)
        raise ValueError(
            f"Unsupported output format '{out_p.suffix}'. Supported formats are: {supported_str}"
        )

    # Collision guards
    in_resolved = in_p.resolve()
    out_resolved = out_p.resolve()
    if in_resolved == out_resolved:
        raise ValueError(
            f"Output path cannot be identical to the original input file: '{output_path}'"
        )

    if rep_p is not None:
        if rep_p.suffix.lower() != ".json":
            raise ValueError(
                f"Invalid report output format '{rep_p.suffix}'. Expected '.json'."
            )
        rep_resolved = rep_p.resolve()
        if rep_resolved == in_resolved:
            raise ValueError("Report path cannot be identical to the original input file.")
        if rep_resolved == out_resolved:
            raise ValueError("Report path cannot be identical to the output file.")

    # Overwrite guards before processing
    if out_p.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: '{output_path}'. Use --overwrite to permit overwriting."
        )

    if rep_p is not None and rep_p.exists() and not overwrite:
        raise FileExistsError(
            f"Report file already exists: '{report_path}'. Use --overwrite to permit overwriting."
        )

    # Step 1: Ingestion
    raw_df = read_file(in_p)
    original_row_count = len(raw_df)

    # Step 2: Column standardization
    std_df = standardize_column_names(raw_df)

    # Step 3: Exact duplicate removal
    cleaned_df, duplicates_removed = remove_duplicate_rows(std_df)
    final_row_count = len(cleaned_df)

    # Step 4: Missing value analysis
    missing_analysis = analyze_missing_values(cleaned_df)

    # Step 5: Suspicious data analysis
    numeric_issues: dict[str, Any] = {}
    date_issues: dict[str, Any] = {}
    warnings: list[str] = []

    if duplicates_removed > 0:
        warnings.append(f"Removed {duplicates_removed} exact duplicate row(s).")

    if numeric_cols:
        for col in numeric_cols:
            target_col = col if col in cleaned_df.columns else standardize_column_name(col)
            if target_col not in cleaned_df.columns:
                raise ValueError(
                    f"Specified numeric column '{col}' not found in dataset columns: {list(cleaned_df.columns)}"
                )
            issues = find_invalid_numeric_values(cleaned_df, target_col)
            if issues:
                numeric_issues[target_col] = issues
                warnings.append(
                    f"Found {len(issues)} suspicious non-numeric value(s) in column '{target_col}'."
                )

    if date_cols:
        for col in date_cols:
            target_col = col if col in cleaned_df.columns else standardize_column_name(col)
            if target_col not in cleaned_df.columns:
                raise ValueError(
                    f"Specified date column '{col}' not found in dataset columns: {list(cleaned_df.columns)}"
                )
            issues = find_invalid_date_values(cleaned_df, target_col, date_format=date_format)
            if issues:
                date_issues[target_col] = issues
                warnings.append(
                    f"Found {len(issues)} unparseable date value(s) in column '{target_col}' with format '{date_format}'."
                )

    suspicious_analysis = (
        SuspiciousValueAnalysis(numeric_issues=numeric_issues, date_issues=date_issues)
        if (numeric_cols or date_cols)
        else None
    )

    # Step 6: File export
    export_cleaned_file(
        cleaned_df,
        output_path=out_p,
        input_path=in_p,
        overwrite=overwrite,
    )

    # Step 7: Report generation
    status = "warning" if warnings else "success"
    report = generate_cleaning_report(
        original_row_count=original_row_count,
        final_row_count=final_row_count,
        duplicate_rows_removed=duplicates_removed,
        missing_analysis=missing_analysis,
        suspicious_analysis=suspicious_analysis,
        input_file=in_p,
        output_file=out_p,
        warnings=warnings,
        status=status,
    )

    # Step 8: Save JSON report if requested
    if rep_p is not None:
        save_report_to_json(report, output_path=rep_p, overwrite=overwrite)

    return report


def main(argv: Union[Sequence[str], None] = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv : Sequence[str] or None, optional
        Command-line argument tokens. If None, sys.argv[1:] is used.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on failure.
    """
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    input_path = args.input or args.input_pos
    output_path = args.output or args.output_pos

    if not input_path:
        sys.stderr.write("Error: Missing required input file. Use -i/--input <PATH>.\n")
        return 1

    if not output_path:
        sys.stderr.write("Error: Missing required output file. Use -o/--output <PATH>.\n")
        return 1

    try:
        report = run_pipeline(
            input_path=input_path,
            output_path=output_path,
            report_path=args.report,
            numeric_cols=args.numeric_cols,
            date_cols=args.date_cols,
            date_format=args.date_format,
            overwrite=args.overwrite,
        )

        # Print concise human-readable summary
        sys.stdout.write("✓ Cleaning completed successfully:\n")
        sys.stdout.write(f"  Input:               {report.get('input_file')}\n")
        sys.stdout.write(f"  Output:              {report.get('output_file')}\n")
        if report.get("report_file") or args.report:
            sys.stdout.write(f"  Report:              {args.report}\n")
        sys.stdout.write(f"  Original rows:       {report.get('original_row_count')}\n")
        sys.stdout.write(f"  Final rows:          {report.get('final_row_count')}\n")
        sys.stdout.write(f"  Duplicates removed:  {report.get('duplicate_rows_removed')}\n")

        missing_data = report.get("missing_values")
        if missing_data:
            sys.stdout.write(f"  Total missing cells: {missing_data.get('total_missing_cells')}\n")

        suspicious_data = report.get("suspicious_data")
        if suspicious_data:
            num_count = sum(len(v) for v in suspicious_data.get("numeric_issues", {}).values())
            dt_count = sum(len(v) for v in suspicious_data.get("date_issues", {}).values())
            sys.stdout.write(f"  Suspicious values:   {num_count + dt_count}\n")

        warnings = report.get("warnings", [])
        if warnings:
            sys.stdout.write("  Warnings:\n")
            for w in warnings:
                sys.stdout.write(f"    - {w}\n")

        return 0

    except (ValueError, FileNotFoundError, FileExistsError, OSError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
