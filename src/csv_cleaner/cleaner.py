"""Data cleaning module for tabular datasets.

This module provides focused functions for standardizing column names and
removing exact duplicate rows from pandas DataFrames.
"""

from typing import Any
import pandas as pd


def standardize_column_name(name: Any) -> str:
    """Standardize a single column name.

    Transformations applied:
    1. Strips leading and trailing whitespace.
    2. Converts all characters to lowercase.
    3. Replaces spaces and hyphens with underscores.

    Parameters
    ----------
    name : Any
        The original column name (typically a string).

    Returns
    -------
    str
        The standardized snake_case column name.

    Raises
    ------
    ValueError
        If the column name is empty, whitespace-only, or null.
    """
    if name is None or pd.isna(name):
        raise ValueError("Column name cannot be empty or null.")

    name_str = str(name).strip()
    if not name_str:
        raise ValueError(f"Column name cannot be empty or whitespace-only: {repr(name)}")

    return name_str.lower().replace(" ", "_").replace("-", "_")


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize all column names of a DataFrame.

    Applies whitespace stripping, lowercase conversion, and space/hyphen
    replacement with underscores to each column header. Validates that no
    two original columns normalize to the same name (collision detection).

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame whose columns should be standardized.

    Returns
    -------
    pandas.DataFrame
        A new DataFrame with standardized column names. The original DataFrame
        is not modified.

    Raises
    ------
    ValueError
        If any column name is empty or if two or more original columns normalize
        to the same standardized name.
    """
    if df.columns.empty:
        return df.copy()

    standardized_cols: list[str] = []
    seen: dict[str, list[str]] = {}

    for col in df.columns:
        std_col = standardize_column_name(col)
        standardized_cols.append(std_col)
        seen.setdefault(std_col, []).append(str(col))

    collisions = {std: origs for std, origs in seen.items() if len(origs) > 1}
    if collisions:
        collision_details = "; ".join(
            f"'{std}' from original columns {origs}"
            for std, origs in collisions.items()
        )
        raise ValueError(f"Column name collision detected: {collision_details}")

    new_df = df.copy()
    new_df.columns = standardized_cols
    return new_df


def remove_duplicate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate rows from a DataFrame, keeping the first occurrence.

    A row is only removed if all column values are identical across all columns.
    Preserves original row ordering and DataFrame indices.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame to deduplicate.

    Returns
    -------
    tuple[pandas.DataFrame, int]
        A tuple of (deduplicated_df, removed_count), where deduplicated_df is a
        new DataFrame with duplicates removed and removed_count is the integer
        count of removed duplicate rows. The original DataFrame is not modified.
    """
    if df.empty:
        return df.copy(), 0

    deduped_df = df.drop_duplicates(keep="first")
    removed_count = len(df) - len(deduped_df)
    return deduped_df.copy(), removed_count
