"""Tests for csv_cleaner.cleaner module."""

import pandas as pd
import pytest

from csv_cleaner.cleaner import (
    remove_duplicate_rows,
    standardize_column_name,
    standardize_column_names,
)


def test_cleaner_module_imports() -> None:
    """Verify that cleaner module can be imported and exports expected functions."""
    import csv_cleaner.cleaner

    assert hasattr(csv_cleaner.cleaner, "standardize_column_name")
    assert hasattr(csv_cleaner.cleaner, "standardize_column_names")
    assert hasattr(csv_cleaner.cleaner, "remove_duplicate_rows")


def test_standard_column_names() -> None:
    """Verify that already standard column names remain unchanged."""
    df = pd.DataFrame({"id": [1, 2], "first_name": ["Alice", "Bob"], "total_score": [95, 88]})
    result_df = standardize_column_names(df)

    assert list(result_df.columns) == ["id", "first_name", "total_score"]


def test_leading_trailing_spaces_and_uppercase_names() -> None:
    """Verify stripping whitespace and lowercasing column names."""
    df = pd.DataFrame({"  First Name  ": ["Alice"], "LAST NAME ": ["Smith"], " AGE": [30]})
    result_df = standardize_column_names(df)

    assert list(result_df.columns) == ["first_name", "last_name", "age"]


def test_spaces_and_hyphens() -> None:
    """Verify replacing spaces and hyphens with underscores."""
    df = pd.DataFrame(
        {
            "user-id": [1],
            "postal-code": ["10001"],
            "first name": ["Alice"],
            "account - type": ["premium"],
        }
    )
    result_df = standardize_column_names(df)

    assert list(result_df.columns) == ["user_id", "postal_code", "first_name", "account___type"]
    assert standardize_column_name("order-item-id") == "order_item_id"
    assert standardize_column_name("shipping address") == "shipping_address"


def test_empty_column_names() -> None:
    """Verify handling empty, whitespace-only, or null column names safely with ValueError."""
    with pytest.raises(ValueError, match="empty|whitespace-only"):
        standardize_column_name("")

    with pytest.raises(ValueError, match="empty|whitespace-only"):
        standardize_column_name("   ")

    with pytest.raises(ValueError, match="empty|null"):
        standardize_column_name(None)

    df_empty_col = pd.DataFrame({"": [1, 2], "valid_col": [3, 4]})
    with pytest.raises(ValueError, match="empty|whitespace-only"):
        standardize_column_names(df_empty_col)


def test_normalization_collisions() -> None:
    """Verify detecting collisions where different original column names normalize identically."""
    # "First Name" and "first-name" both normalize to "first_name"
    df = pd.DataFrame(
        [[1, 2]],
        columns=["First Name", "first-name"],
    )

    with pytest.raises(ValueError, match="collision"):
        standardize_column_names(df)


def test_exact_duplicate_removal() -> None:
    """Verify exact duplicate rows are removed and count of removed rows is returned."""
    df = pd.DataFrame(
        {
            "id": [1, 2, 1, 3, 2],
            "category": ["A", "B", "A", "C", "B"],
        }
    )

    deduped_df, removed_count = remove_duplicate_rows(df)

    assert removed_count == 2
    assert len(deduped_df) == 3
    assert list(deduped_df["id"]) == [1, 2, 3]
    assert list(deduped_df["category"]) == ["A", "B", "C"]


def test_keeping_first_occurrence() -> None:
    """Verify deduplication preserves the first occurrence and its original index."""
    df = pd.DataFrame(
        {
            "code": ["X", "Y", "X"],
            "value": [10, 20, 10],
        },
        index=[100, 200, 300],
    )

    deduped_df, removed_count = remove_duplicate_rows(df)

    assert removed_count == 1
    assert len(deduped_df) == 2
    assert list(deduped_df.index) == [100, 200]
    assert deduped_df.loc[100, "value"] == 10


def test_rows_sharing_one_value_not_removed() -> None:
    """Verify that rows sharing a subset of values but not identical across all columns are retained."""
    df = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "role": ["admin", "user", "admin"],
        }
    )

    deduped_df, removed_count = remove_duplicate_rows(df)

    assert removed_count == 0
    assert len(deduped_df) == 3


def test_empty_dataframes() -> None:
    """Verify behavior on empty DataFrames (0 columns or 0 rows)."""
    # 0 columns, 0 rows
    df_empty = pd.DataFrame()
    std_empty = standardize_column_names(df_empty)
    assert std_empty.empty
    assert len(std_empty.columns) == 0

    deduped_empty, removed_0 = remove_duplicate_rows(df_empty)
    assert deduped_empty.empty
    assert removed_0 == 0

    # 2 columns, 0 rows
    df_empty_with_cols = pd.DataFrame(columns=["User-ID", "Account Type"])
    std_empty_with_cols = standardize_column_names(df_empty_with_cols)
    assert list(std_empty_with_cols.columns) == ["user_id", "account_type"]
    assert len(std_empty_with_cols) == 0

    deduped_empty_cols, removed_1 = remove_duplicate_rows(df_empty_with_cols)
    assert len(deduped_empty_cols) == 0
    assert removed_1 == 0


def test_original_dataframe_is_unchanged() -> None:
    """Verify input DataFrame is not mutated during column standardization or deduplication."""
    original_df = pd.DataFrame(
        {
            "User-ID": [10, 20, 10],
            "Score": [100, 200, 100],
        }
    )
    original_columns = list(original_df.columns)
    original_data = original_df.values.tolist()

    # Test standardize_column_names immutability
    std_df = standardize_column_names(original_df)
    assert list(original_df.columns) == original_columns
    assert original_df.values.tolist() == original_data

    # Mutating returned DataFrame does not affect original
    std_df["new_col"] = [1, 2, 3]
    assert "new_col" not in original_df.columns

    # Test remove_duplicate_rows immutability
    deduped_df, _ = remove_duplicate_rows(original_df)
    assert len(original_df) == 3
    assert list(original_df.columns) == original_columns
    assert original_df.values.tolist() == original_data

    # Mutating deduped DataFrame does not affect original
    deduped_df["extra_col"] = [9, 9]
    assert "extra_col" not in original_df.columns
