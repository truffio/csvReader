"""In-memory CSV data model."""
import csv
import io
import os
from typing import Optional


class CsvModel:
    def __init__(self):
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.path: Optional[str] = None
        self.dirty: bool = False
        self.delimiter: str = ","

    # ---- file handling ----
    def new(self, num_columns: int = 3, num_rows: int = 5) -> None:
        self.headers = [f"Column {i}" for i in range(1, num_columns + 1)]
        self.rows = [["" for _ in range(num_columns)] for _ in range(num_rows)]
        self.path = None
        self.delimiter = ","
        self.dirty = False

    def load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            text = f.read()
        delimiter = ","
        if text.strip():
            try:
                delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        if not records:
            headers: list[str] = []
            rows: list[list[str]] = []
        else:
            headers = list(records[0])
            rows = [list(r) for r in records[1:]]
            width = max([len(headers)] + [len(r) for r in rows])
            for i in range(len(headers) + 1, width + 1):
                headers.append(self._unique_name(headers, i))
            n = len(headers)
            rows = [(r + [""] * (n - len(r)))[:n] for r in rows]
        self.headers = headers
        self.rows = rows
        self.delimiter = delimiter
        self.path = path
        self.dirty = False

    def save(self, path: Optional[str] = None) -> None:
        target = path or self.path
        if not target:
            raise ValueError("No path specified")
        with open(target, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=self.delimiter)
            if self.headers:
                w.writerow(self.headers)
                w.writerows(self.rows)
        self.path = target
        self.dirty = False

    # ---- helpers ----
    @staticmethod
    def _unique_name(existing: list[str], start: int) -> str:
        n = start
        while f"Column {n}" in existing:
            n += 1
        return f"Column {n}"

    def _check_row(self, row: int) -> None:
        if not (0 <= row < len(self.rows)):
            raise IndexError(f"row index out of range: {row}")

    def _check_col(self, col: int) -> None:
        if not (0 <= col < len(self.headers)):
            raise IndexError(f"column index out of range: {col}")

    # ---- queries ----
    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers)

    def get_cell(self, row: int, col: int) -> str:
        self._check_row(row)
        self._check_col(col)
        return self.rows[row][col]

    # ---- mutations ----
    def set_cell(self, row: int, col: int, value: str) -> None:
        self._check_row(row)
        self._check_col(col)
        if self.rows[row][col] != value:
            self.rows[row][col] = value
            self.dirty = True

    def insert_row(self, index: Optional[int] = None) -> int:
        if index is None:
            index = len(self.rows)
        elif not (0 <= index <= len(self.rows)):
            raise IndexError(f"row index out of range: {index}")
        self.rows.insert(index, ["" for _ in self.headers])
        self.dirty = True
        return index

    def delete_rows(self, indices: list[int]) -> None:
        unique = sorted(set(indices), reverse=True)
        for i in unique:
            self._check_row(i)
        for i in unique:
            del self.rows[i]
        if unique:
            self.dirty = True

    def insert_column(self, name: Optional[str] = None, index: Optional[int] = None) -> int:
        if index is None:
            index = len(self.headers)
        elif not (0 <= index <= len(self.headers)):
            raise IndexError(f"column index out of range: {index}")
        if name is None:
            name = self._unique_name(self.headers, len(self.headers) + 1)
        self.headers.insert(index, name)
        for r in self.rows:
            r.insert(index, "")
        self.dirty = True
        return index

    def delete_columns(self, indices: list[int]) -> None:
        unique = sorted(set(indices), reverse=True)
        for i in unique:
            self._check_col(i)
        for i in unique:
            del self.headers[i]
            for r in self.rows:
                del r[i]
        if unique:
            self.dirty = True

    def rename_column(self, col: int, name: str) -> None:
        self._check_col(col)
        if self.headers[col] != name:
            self.headers[col] = name
            self.dirty = True
