from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Country, Fixture, League, Season, Team
from app.db.session import get_db
from app.schemas.catalog import CountryIn, FixtureIn, LeagueIn, SeasonIn, TeamIn

router = APIRouter(prefix="/catalog", tags=["manual data entry"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Data duplikat atau relasi tidak valid") from exc


def _not_found(item, label: str):
    if item is None:
        raise HTTPException(status_code=404, detail=f"{label} tidak ditemukan")
    return item


@router.post("/countries", status_code=201)
def create_country(payload: CountryIn, db: Session = Depends(get_db)):
    item = Country(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return {"id": item.id, "name": item.name, "code": item.code}


@router.get("/countries")
def list_countries(search: str | None = None, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(Country).order_by(Country.name).limit(limit)
    if search:
        stmt = stmt.where(Country.name.ilike(f"%{search.strip()}%"))
    return [{"id": x.id, "name": x.name, "code": x.code} for x in db.scalars(stmt)]


@router.put("/countries/{item_id}")
def update_country(item_id: int, payload: CountryIn, db: Session = Depends(get_db)):
    item = _not_found(db.get(Country, item_id), "Negara")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    _commit(db)
    return {"id": item.id, "name": item.name, "code": item.code}


@router.post("/leagues", status_code=201)
def create_league(payload: LeagueIn, db: Session = Depends(get_db)):
    if payload.country_id is not None and db.get(Country, payload.country_id) is None:
        raise HTTPException(status_code=404, detail="Negara tidak ditemukan")
    item = League(**payload.model_dump())
    db.add(item); _commit(db); db.refresh(item)
    return {"id": item.id, "name": item.name, "country_id": item.country_id, "external_id": item.external_id}


@router.get("/leagues")
def list_leagues(search: str | None = None, country_id: int | None = None, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(League).order_by(League.name).limit(limit)
    if search: stmt = stmt.where(League.name.ilike(f"%{search.strip()}%"))
    if country_id: stmt = stmt.where(League.country_id == country_id)
    return [{"id": x.id, "name": x.name, "country_id": x.country_id, "external_id": x.external_id} for x in db.scalars(stmt)]


@router.put("/leagues/{item_id}")
def update_league(item_id: int, payload: LeagueIn, db: Session = Depends(get_db)):
    item = _not_found(db.get(League, item_id), "Liga")
    if payload.country_id is not None and db.get(Country, payload.country_id) is None:
        raise HTTPException(status_code=404, detail="Negara tidak ditemukan")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    _commit(db)
    return {"id": item.id, "name": item.name, "country_id": item.country_id, "external_id": item.external_id}


@router.post("/seasons", status_code=201)
def create_season(payload: SeasonIn, db: Session = Depends(get_db)):
    if db.get(League, payload.league_id) is None: raise HTTPException(status_code=404, detail="Liga tidak ditemukan")
    item = Season(**payload.model_dump()); db.add(item); _commit(db); db.refresh(item)
    return {"id": item.id, "league_id": item.league_id, "name": item.name, "start_date": item.start_date, "end_date": item.end_date}


@router.get("/seasons")
def list_seasons(league_id: int | None = None, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(Season).order_by(Season.name.desc()).limit(limit)
    if league_id: stmt = stmt.where(Season.league_id == league_id)
    return [{"id": x.id, "league_id": x.league_id, "name": x.name, "start_date": x.start_date, "end_date": x.end_date} for x in db.scalars(stmt)]


@router.put("/seasons/{item_id}")
def update_season(item_id: int, payload: SeasonIn, db: Session = Depends(get_db)):
    item = _not_found(db.get(Season, item_id), "Musim")
    if db.get(League, payload.league_id) is None: raise HTTPException(status_code=404, detail="Liga tidak ditemukan")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    _commit(db)
    return {"id": item.id, "league_id": item.league_id, "name": item.name, "start_date": item.start_date, "end_date": item.end_date}


@router.post("/teams", status_code=201)
def create_team(payload: TeamIn, db: Session = Depends(get_db)):
    item = Team(**payload.model_dump()); db.add(item); _commit(db); db.refresh(item)
    return {"id": item.id, "name": item.name, "country_code": item.country_code, "external_id": item.external_id}


@router.get("/teams")
def list_teams(search: str | None = None, country_code: str | None = None, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(Team).order_by(Team.name).limit(limit)
    if search: stmt = stmt.where(Team.name.ilike(f"%{search.strip()}%"))
    if country_code: stmt = stmt.where(Team.country_code == country_code.upper())
    return [{"id": x.id, "name": x.name, "country_code": x.country_code, "external_id": x.external_id} for x in db.scalars(stmt)]


@router.put("/teams/{item_id}")
def update_team(item_id: int, payload: TeamIn, db: Session = Depends(get_db)):
    item = _not_found(db.get(Team, item_id), "Tim")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    _commit(db)
    return {"id": item.id, "name": item.name, "country_code": item.country_code, "external_id": item.external_id}


@router.post("/fixtures", status_code=201)
def create_fixture(payload: FixtureIn, db: Session = Depends(get_db)):
    if db.get(Season, payload.season_id) is None: raise HTTPException(status_code=404, detail="Musim tidak ditemukan")
    for team_id in (payload.home_team_id, payload.away_team_id):
        if db.get(Team, team_id) is None: raise HTTPException(status_code=404, detail=f"Tim {team_id} tidak ditemukan")
    item = Fixture(**payload.model_dump()); db.add(item); _commit(db); db.refresh(item)
    return _fixture_dict(item)


@router.get("/fixtures")
def list_fixtures(season_id: int | None = None, team_id: int | None = None, status: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    stmt = select(Fixture).order_by(Fixture.kickoff_at.desc()).limit(limit)
    if season_id: stmt = stmt.where(Fixture.season_id == season_id)
    if team_id: stmt = stmt.where((Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id))
    if status: stmt = stmt.where(Fixture.status == status.lower())
    return [_fixture_dict(x) for x in db.scalars(stmt)]


@router.put("/fixtures/{item_id}")
def update_fixture(item_id: int, payload: FixtureIn, db: Session = Depends(get_db)):
    item = _not_found(db.get(Fixture, item_id), "Pertandingan")
    if db.get(Season, payload.season_id) is None: raise HTTPException(status_code=404, detail="Musim tidak ditemukan")
    for team_id in (payload.home_team_id, payload.away_team_id):
        if db.get(Team, team_id) is None: raise HTTPException(status_code=404, detail=f"Tim {team_id} tidak ditemukan")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    _commit(db)
    return _fixture_dict(item)


def _fixture_dict(item: Fixture) -> dict:
    return {"id": item.id, "season_id": item.season_id, "home_team_id": item.home_team_id,
            "away_team_id": item.away_team_id, "kickoff_at": item.kickoff_at.isoformat(),
            "status": item.status, "home_goals": item.home_goals, "away_goals": item.away_goals}



def _delete_if_unused(db: Session, model, item_id: int, label: str, references: list[tuple[object, object]]) -> dict:
    item = _not_found(db.get(model, item_id), label)
    for related_model, foreign_key in references:
        count = db.scalar(select(related_model).where(foreign_key == item_id).limit(1))
        if count is not None:
            raise HTTPException(status_code=409, detail=f"{label} tidak dapat dihapus karena masih digunakan oleh data terkait")
    db.delete(item)
    _commit(db)
    return {"deleted": True, "id": item_id}


@router.delete("/countries/{item_id}")
def delete_country(item_id: int, db: Session = Depends(get_db)):
    return _delete_if_unused(db, Country, item_id, "Negara", [(League, League.country_id)])


@router.delete("/leagues/{item_id}")
def delete_league(item_id: int, db: Session = Depends(get_db)):
    return _delete_if_unused(db, League, item_id, "Liga", [(Season, Season.league_id)])


@router.delete("/seasons/{item_id}")
def delete_season(item_id: int, db: Session = Depends(get_db)):
    return _delete_if_unused(db, Season, item_id, "Musim", [(Fixture, Fixture.season_id)])


@router.delete("/teams/{item_id}")
def delete_team(item_id: int, db: Session = Depends(get_db)):
    return _delete_if_unused(db, Team, item_id, "Tim", [
        (Fixture, Fixture.home_team_id), (Fixture, Fixture.away_team_id)
    ])


@router.delete("/fixtures/{item_id}")
def delete_fixture(item_id: int, db: Session = Depends(get_db)):
    return _delete_if_unused(db, Fixture, item_id, "Pertandingan", [])
