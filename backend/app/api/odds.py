from datetime import datetime, timezone
import csv
import io
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Bookmaker, Fixture, ImportBatch, OddsQuote
from app.db.session import get_db
from app.schemas.odds import BookmakerIn, OddsQuoteIn

router = APIRouter(prefix="/odds", tags=["historical odds"])
MAX_ODDS_FILE_BYTES = 10 * 1024 * 1024
MAX_ODDS_ROWS = 50000
ODDS_COLUMNS = ("fixture_id", "bookmaker", "market", "selection", "line", "decimal_odds", "captured_at", "quote_type", "source", "source_ref")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bookmaker_dict(item: Bookmaker) -> dict:
    return {"id": item.id, "name": item.name, "provider_key": item.provider_key, "enabled": item.enabled}


def _quote_dict(item: OddsQuote) -> dict:
    return {
        "id": item.id, "fixture_id": item.fixture_id, "bookmaker_id": item.bookmaker_id,
        "bookmaker_name": item.bookmaker.name, "market": item.market, "selection": item.selection,
        "line": str(item.line) if item.line is not None else None,
        "decimal_odds": str(item.decimal_odds), "captured_at": item.captured_at.isoformat(),
        "quote_type": item.quote_type, "source": item.source, "source_ref": item.source_ref,
    }


@router.post("/bookmakers", status_code=201)
def create_bookmaker(payload: BookmakerIn, db: Session = Depends(get_db)):
    item = Bookmaker(name=payload.name, provider_key=payload.provider_key)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bookmaker dengan nama tersebut sudah ada") from exc
    db.refresh(item)
    return _bookmaker_dict(item)


@router.get("/bookmakers")
def list_bookmakers(db: Session = Depends(get_db)):
    return [_bookmaker_dict(x) for x in db.scalars(select(Bookmaker).order_by(Bookmaker.name))]


def _validate_quote_row(row: dict[str, Any], row_number: int, db: Session, bookmaker_cache: dict[str, Bookmaker]):
    problems = []
    try:
        fixture_id = int(str(row.get("fixture_id", "")).strip())
    except (TypeError, ValueError):
        fixture_id = 0
        problems.append("fixture_id harus berupa bilangan bulat positif")
    if fixture_id < 1 and not problems:
        problems.append("fixture_id harus lebih dari 0")
    bookmaker_name = str(row.get("bookmaker") or "").strip()
    bookmaker = bookmaker_cache.get(bookmaker_name.casefold())
    if not bookmaker and bookmaker_name:
        bookmaker = db.scalar(select(Bookmaker).where(Bookmaker.name.ilike(bookmaker_name)))
        if bookmaker:
            bookmaker_cache[bookmaker_name.casefold()] = bookmaker
    if not bookmaker:
        problems.append(f"Bookmaker '{bookmaker_name}' tidak ditemukan")
    fixture = db.get(Fixture, fixture_id) if fixture_id > 0 else None
    if fixture is None:
        problems.append(f"Fixture ID {fixture_id} tidak ditemukan")
    line_raw = str(row.get("line") or "").strip()
    payload = None
    try:
        payload = OddsQuoteIn(
            fixture_id=fixture_id, bookmaker_id=bookmaker.id if bookmaker else 1,
            market=str(row.get("market") or "").strip().lower(),
            selection=str(row.get("selection") or "").strip().lower(),
            line=Decimal(line_raw) if line_raw else None,
            decimal_odds=Decimal(str(row.get("decimal_odds") or "").strip()),
            captured_at=str(row.get("captured_at") or "").strip(),
            quote_type=str(row.get("quote_type") or "").strip().lower(),
            source=(str(row.get("source") or "manual").strip().lower() or "manual"),
            source_ref=(str(row.get("source_ref") or "").strip() or None),
        )
    except Exception as exc:
        problems.append(str(exc).splitlines()[0][:240])
    if payload and fixture:
        captured = _aware_utc(payload.captured_at)
        kickoff = _aware_utc(fixture.kickoff_at)
        if payload.quote_type == "live" and captured < kickoff:
            problems.append("Odds live tidak boleh tercatat sebelum kickoff")
        if payload.quote_type != "live" and captured > kickoff:
            problems.append("Odds pre-match harus tercatat sebelum atau saat kickoff")
    if problems:
        return None, {"row": row_number, "errors": problems}
    return (payload, bookmaker), None


def _read_odds_csv(raw: bytes) -> list[dict[str, Any]]:
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail={"message": "File harus menggunakan encoding UTF-8", "invalid_rows": [{"row": 1, "errors": ["Encoding UTF-8 tidak valid"]}]}) from exc
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    missing = [x for x in ODDS_COLUMNS if x not in headers]
    if missing or len(headers) != len(set(headers)):
        raise HTTPException(status_code=422, detail={"message": "Header CSV tidak valid", "invalid_rows": [{"row": 1, "errors": ([f"Kolom wajib hilang: {', '.join(missing)}"] if missing else ["Nama kolom duplikat"])}]})
    rows = list(reader)
    if len(rows) > MAX_ODDS_ROWS:
        raise HTTPException(status_code=422, detail={"message": f"Maksimal {MAX_ODDS_ROWS} baris", "invalid_rows": []})
    return rows


def _read_odds_excel(raw: bytes) -> list[dict[str, Any]]:
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"message": "File Excel tidak valid", "invalid_rows": [{"row": 1, "errors": ["File Excel rusak atau tidak valid"]}]}) from exc
    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, None)
        headers = [str(x).strip() if x is not None else "" for x in (header or [])]
        missing = [x for x in ODDS_COLUMNS if x not in headers]
        if missing or len(headers) != len(set(headers)):
            raise HTTPException(status_code=422, detail={"message": "Header Excel tidak valid", "invalid_rows": [{"row": 1, "errors": ([f"Kolom wajib hilang: {', '.join(missing)}"] if missing else ["Nama kolom duplikat"])}]})
        rows = []
        for values in iterator:
            if not any(x is not None and str(x).strip() for x in values):
                continue
            row = dict(zip(headers, values))
            if isinstance(row.get("captured_at"), datetime):
                row["captured_at"] = row["captured_at"].isoformat()
            rows.append(row)
            if len(rows) > MAX_ODDS_ROWS:
                raise HTTPException(status_code=422, detail={"message": f"Maksimal {MAX_ODDS_ROWS} baris", "invalid_rows": []})
        return rows
    finally:
        workbook.close()


def _import_odds_rows(rows: list[dict[str, Any]], filename: str, file_format: str, db: Session) -> dict:
    errors = []
    validated = []
    cache: dict[str, Bookmaker] = {}
    for number, row in enumerate(rows, start=2):
        parsed, error = _validate_quote_row(row, number, db, cache)
        if error:
            errors.append(error)
        else:
            validated.append(parsed)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Validasi odds gagal; tidak ada data disimpan", "invalid_rows": errors[:500]})
    seen = set()
    duplicates = 0
    new_quotes = []
    for payload, bookmaker in validated:
        captured = _aware_utc(payload.captured_at)
        key = (payload.fixture_id, bookmaker.id, payload.market, payload.selection, str(payload.line), captured.isoformat())
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        stmt = select(OddsQuote.id).where(
            OddsQuote.fixture_id == payload.fixture_id, OddsQuote.bookmaker_id == bookmaker.id,
            OddsQuote.market == payload.market, OddsQuote.selection == payload.selection,
            OddsQuote.captured_at == captured,
        )
        stmt = stmt.where(OddsQuote.line.is_(None) if payload.line is None else OddsQuote.line == payload.line)
        if db.scalar(stmt.limit(1)) is not None:
            duplicates += 1
            continue
        new_quotes.append(OddsQuote(
            fixture_id=payload.fixture_id, bookmaker_id=bookmaker.id, market=payload.market,
            selection=payload.selection, line=payload.line, decimal_odds=payload.decimal_odds,
            captured_at=captured, quote_type=payload.quote_type, source=payload.source,
            source_ref=payload.source_ref,
        ))
    try:
        db.add_all(new_quotes)
        db.flush()
        db.add(ImportBatch(filename=filename[:255], file_format=file_format, status="completed",
            rows_received=len(rows), imported=len(new_quotes), duplicates_skipped=duplicates,
            invalid_rows=0, message="Odds historis berhasil diimpor"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "completed", "rows_received": len(rows), "imported": len(new_quotes),
            "duplicates_skipped": duplicates, "invalid_rows": 0, "message": "Odds historis berhasil diimpor"}


async def _upload_odds(file: UploadFile, db: Session, expected: str) -> dict:
    filename = file.filename or ("odds." + expected)
    if not filename.lower().endswith("." + expected):
        raise HTTPException(status_code=415, detail=f"Format file harus .{expected}")
    raw = await file.read(MAX_ODDS_FILE_BYTES + 1)
    if len(raw) > MAX_ODDS_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 10 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="File kosong")
    rows = _read_odds_csv(raw) if expected == "csv" else _read_odds_excel(raw)
    try:
        return _import_odds_rows(rows, filename, "odds_" + expected, db)
    except HTTPException as exc:
        db.rollback()
        db.add(ImportBatch(filename=filename[:255], file_format="odds_" + expected, status="failed",
            rows_received=len(rows), imported=0, duplicates_skipped=0,
            invalid_rows=len((exc.detail or {}).get("invalid_rows", [])) if isinstance(exc.detail, dict) else 0,
            message="Validasi odds gagal; tidak ada data disimpan"))
        db.commit()
        raise


@router.post("/import/csv")
async def import_odds_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await _upload_odds(file, db, "csv")


@router.post("/import/excel")
async def import_odds_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await _upload_odds(file, db, "xlsx")


@router.get("/templates/csv")
def download_odds_csv_template():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(ODDS_COLUMNS)
    writer.writerow([1, "Example Bookmaker", "1x2", "home", "", "2.1500", "2026-11-30T18:00:00+07:00", "opening", "manual", ""])
    from fastapi.responses import StreamingResponse
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="betting-intelligence-odds-template.csv"'})


@router.get("/templates/excel")
def download_odds_excel_template():
    from openpyxl import Workbook
    from fastapi.responses import StreamingResponse
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Odds"
    sheet.append(list(ODDS_COLUMNS))
    sheet.append([1, "Example Bookmaker", "1x2", "home", None, 2.15, "2026-11-30T18:00:00+07:00", "opening", "manual", None])
    sheet.freeze_panes = "A2"
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="betting-intelligence-odds-template.xlsx"'})


@router.post("/quotes", status_code=201)
def create_odds_quote(payload: OddsQuoteIn, db: Session = Depends(get_db)):
    fixture = db.get(Fixture, payload.fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Pertandingan tidak ditemukan")
    bookmaker = db.get(Bookmaker, payload.bookmaker_id)
    if bookmaker is None:
        raise HTTPException(status_code=404, detail="Bookmaker tidak ditemukan")
    captured = _aware_utc(payload.captured_at)
    kickoff = _aware_utc(fixture.kickoff_at)
    if payload.quote_type == "live" and captured < kickoff:
        raise HTTPException(status_code=422, detail="Odds live tidak boleh tercatat sebelum kickoff")
    if payload.quote_type != "live" and captured > kickoff:
        raise HTTPException(status_code=422, detail="Odds pre-match harus tercatat sebelum atau saat kickoff")
    duplicate_stmt = select(OddsQuote).where(
        OddsQuote.fixture_id == payload.fixture_id,
        OddsQuote.bookmaker_id == payload.bookmaker_id,
        OddsQuote.market == payload.market,
        OddsQuote.selection == payload.selection,
        OddsQuote.captured_at == captured,
    )
    duplicate_stmt = duplicate_stmt.where(
        OddsQuote.line.is_(None) if payload.line is None else OddsQuote.line == payload.line
    )
    if db.scalar(duplicate_stmt.limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Snapshot odds yang sama sudah tersimpan")
    item = OddsQuote(
        fixture_id=payload.fixture_id, bookmaker_id=payload.bookmaker_id, market=payload.market,
        selection=payload.selection, line=payload.line, decimal_odds=payload.decimal_odds,
        captured_at=captured, quote_type=payload.quote_type, source=payload.source,
        source_ref=payload.source_ref,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Snapshot odds duplikat atau relasi tidak valid") from exc
    db.refresh(item)
    return _quote_dict(item)


@router.get("/fixtures/{fixture_id}/quotes")
def list_fixture_odds(
    fixture_id: int,
    bookmaker_id: int | None = Query(default=None, ge=1),
    market: str | None = Query(default=None, min_length=1, max_length=40),
    quote_type: str | None = Query(default=None, pattern="^(opening|current|closing|live)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    if db.get(Fixture, fixture_id) is None:
        raise HTTPException(status_code=404, detail="Pertandingan tidak ditemukan")
    stmt = select(OddsQuote).where(OddsQuote.fixture_id == fixture_id)
    if bookmaker_id is not None:
        stmt = stmt.where(OddsQuote.bookmaker_id == bookmaker_id)
    if market:
        stmt = stmt.where(OddsQuote.market == market)
    if quote_type:
        stmt = stmt.where(OddsQuote.quote_type == quote_type)
    stmt = stmt.order_by(OddsQuote.captured_at.desc(), OddsQuote.id.desc()).limit(limit)
    return [_quote_dict(x) for x in db.scalars(stmt)]
