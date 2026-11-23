from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.csv_import import ImportValidationError, import_fixtures_csv
from app.services.excel_import import import_fixtures_excel

router = APIRouter(prefix="/imports", tags=["data import"])
MAX_FILE_BYTES = 10 * 1024 * 1024


@router.post("/fixtures/csv", summary="Import fixture results from CSV")
async def upload_fixtures_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=415, detail="Format file harus .csv")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 10 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="File CSV kosong")
    try:
        return import_fixtures_csv(db, raw)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail={
            "message": "Validasi CSV gagal; tidak ada data yang disimpan",
            "invalid_rows": exc.errors,
        }) from exc


@router.post("/fixtures/excel", summary="Import fixture results from Excel workbook")
async def upload_fixtures_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Format file harus .xlsx")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 10 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="File Excel kosong")
    try:
        return import_fixtures_excel(db, raw)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail={
            "message": "Validasi Excel gagal; tidak ada data yang disimpan",
            "invalid_rows": exc.errors,
        }) from exc
