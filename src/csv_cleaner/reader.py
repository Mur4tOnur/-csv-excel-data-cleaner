"""File reader module for CSV and Excel files.

This module provides functionality to safely ingest tabular data from CSV and
XLSX files into pandas DataFrames, performing path and format validation.
"""

from pathlib import Path
from typing import Final, Union

import pandas as pd

SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = (".csv", ".xlsx")


def read_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """Read a CSV or XLSX file into a pandas DataFrame.

    Parameters
    ----------
    file_path : str or pathlib.Path
        The path to the input CSV or Excel file.

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing the tabular data read from the input file.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the path points to a directory, if the file extension is not
        supported, or if the file cannot be parsed or read.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: '{file_path}'")

    if not path.is_file():
        raise ValueError(f"Expected a file, but found a directory: '{file_path}'")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported_str = ", ".join(SUPPORTED_EXTENSIONS)
        raise ValueError(
            f"Unsupported file format '{path.suffix}'. Supported formats are: {supported_str}"
        )

    try:
        if suffix == ".csv":
            return pd.read_csv(path)
        else:  # .xlsx
            return pd.read_excel(path, engine="openpyxl")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"The CSV file is empty: '{file_path}'") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read file '{file_path}': {exc}") from exc
