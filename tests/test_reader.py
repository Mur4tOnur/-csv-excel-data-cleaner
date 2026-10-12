"""Tests for csv_cleaner.reader module."""

from pathlib import Path

import pandas as pd
import pytest

from csv_cleaner.reader import SUPPORTED_EXTENSIONS, read_file


def test_reader_module_imports() -> None:
    """Verify that reader module can be imported and exports expected objects."""
    import csv_cleaner.reader

    assert hasattr(csv_cleaner.reader, "read_file")
    assert hasattr(csv_cleaner.reader, "SUPPORTED_EXTENSIONS")


def test_read_valid_csv(tmp_path: Path) -> None:
    """Verify reading a well-formed CSV file into a pandas DataFrame."""
    csv_file = tmp_path / "sample.csv"
    csv_content = "id,name,amount\n1,Alice,100.5\n2,Bob,250.0\n"
    csv_file.write_text(csv_content, encoding="utf-8")

    df = read_file(csv_file)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "name", "amount"]
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Alice"
    assert df.iloc[1]["amount"] == 250.0


def test_read_valid_xlsx(tmp_path: Path) -> None:
    """Verify reading a well-formed XLSX file into a pandas DataFrame."""
    xlsx_file = tmp_path / "sample.xlsx"
    expected_df = pd.DataFrame(
        {
            "product_id": [101, 102],
            "product_name": ["Widget", "Gadget"],
            "price": [19.99, 49.99],
        }
    )
    expected_df.to_excel(xlsx_file, index=False, engine="openpyxl")

    df = read_file(xlsx_file)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["product_id", "product_name", "price"]
    assert len(df) == 2
    assert df.iloc[0]["product_name"] == "Widget"
    assert df.iloc[1]["price"] == 49.99


def test_read_missing_file(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised when target file does not exist."""
    missing_file = tmp_path / "nonexistent.csv"

    with pytest.raises(FileNotFoundError, match="File not found"):
        read_file(missing_file)


def test_read_unsupported_extension(tmp_path: Path) -> None:
    """Verify ValueError is raised when file extension is not supported."""
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("plain text data", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file format"):
        read_file(txt_file)


def test_read_directory_path(tmp_path: Path) -> None:
    """Verify ValueError is raised if target path is a directory."""
    with pytest.raises(ValueError, match="Expected a file, but found a directory"):
        read_file(tmp_path)


def test_read_empty_csv(tmp_path: Path) -> None:
    """Verify ValueError is raised with clear message if CSV file is empty."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="The CSV file is empty"):
        read_file(empty_csv)


def test_read_uppercase_extension(tmp_path: Path) -> None:
    """Verify that case-insensitive extensions (.CSV, .XLSX) are supported."""
    csv_file = tmp_path / "data.CSV"
    csv_file.write_text("col1,col2\n10,20\n", encoding="utf-8")

    df = read_file(csv_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert list(df.columns) == ["col1", "col2"]


def test_read_does_not_modify_original_file(tmp_path: Path) -> None:
    """Verify that reading a file does not alter the original file on disk."""
    csv_file = tmp_path / "immutable.csv"
    original_content = "a,b,c\n1,2,3\n4,5,6\n"
    csv_file.write_text(original_content, encoding="utf-8")

    mtime_before = csv_file.stat().st_mtime_ns
    df = read_file(csv_file)

    assert csv_file.read_text(encoding="utf-8") == original_content
    assert csv_file.stat().st_mtime_ns == mtime_before
    # Modifying the returned DataFrame must not affect the file
    df["new_col"] = 999
    assert "new_col" not in csv_file.read_text(encoding="utf-8")


def test_read_corrupted_xlsx(tmp_path: Path) -> None:
    """Verify ValueError is raised when Excel file content is corrupted or invalid."""
    corrupted_xlsx = tmp_path / "corrupted.xlsx"
    corrupted_xlsx.write_bytes(b"not an excel spreadsheet binary")

    with pytest.raises(ValueError, match="Failed to read file"):
        read_file(corrupted_xlsx)

