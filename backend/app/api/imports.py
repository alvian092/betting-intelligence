from io import BytesIO, StringIO
import csv
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Fixture, ImportBatch, League, Season, Team
from app.db.session import get_db
from app.services.csv_import import ImportValidationError, REQUIRED_COLUMNS, import_fixtures_csv
from app.services.excel_import import import_fixtures_excel

router = APIRouter(prefix="/imports", tags=["data import"])
MAX_FILE_BYTES = 10 * 1024 * 1024


def _record(db: Session, filename: str, file_format: str, status: str,
            result: dict | None = None, message: str = "", invalid_rows: int = 0) -> None:
    result = result or {}
    db.add(ImportBatch(
        filename=filename[:255], file_format=file_format, status=status,
        rows_received=int(result.get("rows_received", 0)),
        imported=int(result.get("imported", 0)),
        duplicates_skipped=int(result.get("duplicates_skipped", 0)),
        invalid_rows=invalid_rows, message=(message or result.get("message", ""))[:500],
    ))
    db.commit()


@router.get("/templates/fixtures.csv", summary="Download CSV fixture template")
def download_csv_template():
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(REQUIRED_COLUMNS)
    writer.writerow(["2025-08-15", "Premier League", "2025-2026", "Liverpool", "Bournemouth", 4, 2])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="betting-intelligence-fixtures-template.csv"'})


@router.get("/templates/fixtures.xlsx", summary="Download Excel fixture template")
def download_excel_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Fixtures"
    sheet.append(list(REQUIRED_COLUMNS))
    sheet.append(["2025-08-15", "Premier League", "2025-2026", "Liverpool", "Bournemouth", 4, 2])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:G2"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="betting-intelligence-fixtures-template.xlsx"'})



@router.get("/fixtures/export.sqlite", summary="Export fixture database as SQLite")
def export_sqlite_fixtures(db: Session = Depends(get_db)):
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO metadata(key, value) VALUES ('schema_version', '1')")
    connection.execute("CREATE TABLE fixtures (date TEXT NOT NULL, league TEXT NOT NULL, season TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL, home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL)")
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    records = db.execute(
        select(Fixture, Season, League, HomeTeam, AwayTeam)
        .join(Season, Fixture.season_id == Season.id)
        .join(League, Season.league_id == League.id)
        .join(HomeTeam, Fixture.home_team_id == HomeTeam.id)
        .join(AwayTeam, Fixture.away_team_id == AwayTeam.id)
        .where(Fixture.home_goals.is_not(None), Fixture.away_goals.is_not(None))
        .order_by(Fixture.kickoff_at)
    ).all()
    rows = [(f.kickoff_at.date().isoformat(), l.name, s.name, h.name, a.name, f.home_goals, f.away_goals) for f, s, l, h, a in records]
    connection.executemany("INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    payload = connection.serialize()
    connection.close()
    return StreamingResponse(BytesIO(payload), media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": 'attachment; filename="betting-intelligence-fixtures.sqlite"'})

@router.get("/history", summary="List recent import batches")
def list_import_history(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    limit = max(1, min(limit, 100))
    batches = db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc()).limit(limit)).all()
    return {"items": [{
        "id": item.id, "filename": item.filename, "format": item.file_format,
        "status": item.status, "rows_received": item.rows_received,
        "imported": item.imported, "duplicates_skipped": item.duplicates_skipped,
        "invalid_rows": item.invalid_rows, "message": item.message,
        "created_at": item.created_at.isoformat(),
    } for item in batches]}


async def _upload(file: UploadFile, db: Session, expected: str) -> dict:
    filename = file.filename or ("upload." + expected)
    if not filename.lower().endswith("." + expected):
        raise HTTPException(status_code=415, detail="Format file harus ." + expected)
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 10 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="File kosong")
    try:
        result = import_fixtures_csv(db, raw) if expected == "csv" else import_fixtures_excel(db, raw) if expected == "xlsx" else _import_sqlite_bytes(db, raw)
        _record(db, filename, expected, "completed", result=result)
        return result
    except ImportValidationError as exc:
        _record(db, filename, expected, "failed", message="Validasi file gagal; tidak ada data disimpan", invalid_rows=len(exc.errors))
        raise HTTPException(status_code=422, detail={
            "message": f"Validasi {expected.upper()} gagal; tidak ada data yang disimpan",
            "invalid_rows": exc.errors,
        }) from exc


@router.post("/fixtures/csv", summary="Import fixture results from CSV")
async def upload_fixtures_csv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    return await _upload(file, db, "csv")


@router.post("/fixtures/excel", summary="Import fixture results from Excel workbook")
async def upload_fixtures_excel(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    return await _upload(file, db, "xlsx")

def _import_sqlite_bytes(db: Session, raw: bytes) -> dict:
    import tempfile
    from pathlib import Path
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temporary:
            temporary.write(raw)
            temporary_path = temporary.name
        source = sqlite3.connect("file:" + temporary_path + "?mode=ro", uri=True)
        source.execute("PRAGMA query_only = ON")
        integrity = source.execute("PRAGMA quick_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("Database SQLite rusak")
        objects = source.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        if set(objects) != {("table", "metadata"), ("table", "fixtures")}:
            raise ValueError("Gunakan file export SQLite Betting Intelligence")
        version = source.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
        if version != ("1",):
            raise ValueError("Versi skema SQLite tidak didukung")
        columns = [row[1] for row in source.execute("PRAGMA table_info(fixtures)").fetchall()]
        expected = ["date", "league", "season", "home_team", "away_team", "home_goals", "away_goals"]
        if columns != expected:
            raise ValueError("Kolom tabel fixtures tidak sesuai")
        count = source.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
        if count > 50000:
            raise ValueError("Maksimal 50.000 baris per file import")
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(expected)
        writer.writerows(source.execute("SELECT date, league, season, home_team, away_team, home_goals, away_goals FROM fixtures"))
        source.close()
        return import_fixtures_csv(db, output.getvalue().encode("utf-8"))
    except (sqlite3.Error, ValueError) as exc:
        raise ImportValidationError([{"row": 1, "errors": [str(exc) or "File SQLite tidak valid"]}]) from exc
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


@router.post("/fixtures/sqlite", summary="Import Betting Intelligence SQLite export")
async def upload_fixtures_sqlite(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    return await _upload(file, db, "sqlite")
