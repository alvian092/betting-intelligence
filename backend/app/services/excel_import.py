import csv
import io
from datetime import date, datetime
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.services.csv_import import ImportValidationError, REQUIRED_COLUMNS, import_fixtures_csv

MAX_ROWS = 50_000


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def import_fixtures_excel(db: Session, raw: bytes) -> dict[str, Any]:
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except (BadZipFile, OSError, ValueError) as exc:
        raise ImportValidationError([{"row": 1, "errors": ["File Excel tidak valid atau rusak"]}]) from exc

    try:
        worksheet = workbook.active
        iterator = worksheet.iter_rows(values_only=True)
        header_values = next(iterator, None)
        if not header_values:
            raise ImportValidationError([{"row": 1, "errors": ["Worksheet kosong"]}])

        headers = [_cell_to_text(value) for value in header_values]
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            raise ImportValidationError([{
                "row": 1,
                "errors": [f"Kolom wajib tidak ditemukan: {', '.join(missing)}"],
            }])
        if len(headers) != len(set(headers)):
            raise ImportValidationError([{"row": 1, "errors": ["Nama kolom duplikat"]}])

        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        row_count = 0
        for row in iterator:
            values = list(row)
            if not any(value is not None and str(value).strip() for value in values):
                continue
            row_count += 1
            if row_count > MAX_ROWS:
                raise ImportValidationError([{
                    "row": 1,
                    "errors": [f"Maksimal {MAX_ROWS} baris per file"],
                }])
            writer.writerow([_cell_to_text(value) for value in values])

        return import_fixtures_csv(db, output.getvalue().encode("utf-8"))
    finally:
        workbook.close()
