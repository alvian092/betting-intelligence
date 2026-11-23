from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Bookmaker, Fixture, OddsQuote
from app.db.session import get_db
from app.schemas.odds import BookmakerIn, OddsQuoteIn

router = APIRouter(prefix="/odds", tags=["historical odds"])


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
