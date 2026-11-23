import csv
import io
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Fixture, League, Season, Team

REQUIRED_COLUMNS = (
    "date", "league", "season", "home_team", "away_team",
    "home_goals", "away_goals",
)
MAX_ROWS = 50_000


class ImportValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__("CSV validation failed")


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_date(value: str, row: int) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date harus berformat YYYY-MM-DD") from exc


def _parse_goals(value: str, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} harus berupa bilangan bulat") from exc
    if number < 0:
        raise ValueError(f"{field} tidak boleh negatif")
    return number


def _get_or_create_team(db: Session, name: str) -> Team:
    matches = db.scalars(select(Team).where(Team.name.ilike(name))).all()
    if matches:
        return matches[0]
    team = Team(name=name)
    db.add(team)
    db.flush()
    return team


def import_fixtures_csv(db: Session, raw: bytes) -> dict[str, Any]:
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportValidationError([{"row": 1, "errors": ["File harus menggunakan encoding UTF-8"]}]) from exc

    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ImportValidationError([{"row": 1, "errors": [f"Kolom wajib tidak ditemukan: {', '.join(missing)}"]}])
    if len(headers) != len(set(headers)):
        raise ImportValidationError([{"row": 1, "errors": ["Nama kolom duplikat"]}])

    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise ImportValidationError([{"row": 1, "errors": [f"Maksimal {MAX_ROWS} baris per file"]}])

    errors: list[dict[str, Any]] = []
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    duplicates = 0

    for row_number, row in enumerate(rows, start=2):
        problems: list[str] = []
        try:
            raw_date = _clean(row.get("date"))
            match_date = _parse_date(raw_date, row_number)
        except ValueError as exc:
            problems.append(str(exc))
            match_date = None

        league_name = _clean(row.get("league"))
        season_name = _clean(row.get("season"))
        home_name = _clean(row.get("home_team"))
        away_name = _clean(row.get("away_team"))
        if not league_name:
            problems.append("league wajib diisi")
        if not season_name:
            problems.append("season wajib diisi")
        if not home_name or not away_name:
            problems.append("home_team dan away_team wajib diisi")
        if home_name and away_name and home_name.casefold() == away_name.casefold():
            problems.append("Tim kandang dan tandang tidak boleh sama")
        try:
            home_goals = _parse_goals(_clean(row.get("home_goals")), "home_goals")
        except ValueError as exc:
            problems.append(str(exc))
            home_goals = None
        try:
            away_goals = _parse_goals(_clean(row.get("away_goals")), "away_goals")
        except ValueError as exc:
            problems.append(str(exc))
            away_goals = None

        if problems:
            errors.append({"row": row_number, "errors": problems})
            continue

        identity = (match_date.isoformat(), league_name.casefold(), season_name.casefold(),
                    home_name.casefold() + "|" + away_name.casefold())
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        parsed.append({
            "date": match_date, "league": league_name, "season": season_name,
            "home": home_name, "away": away_name,
            "home_goals": home_goals, "away_goals": away_goals,
            "identity": identity,
        })

    if errors:
        raise ImportValidationError(errors)

    imported = 0
    duplicate_existing = 0
    try:
        for item in parsed:
            league = db.scalar(select(League).where(
                League.country_id.is_(None), League.name.ilike(item["league"])
            ))
            if league is None:
                league = League(name=item["league"])
                db.add(league)
                db.flush()

            season = db.scalar(select(Season).where(
                Season.league_id == league.id, Season.name.ilike(item["season"])
            ))
            if season is None:
                season = Season(league_id=league.id, name=item["season"])
                db.add(season)
                db.flush()

            home = _get_or_create_team(db, item["home"])
            away = _get_or_create_team(db, item["away"])
            kickoff = datetime.combine(item["date"], time.min, tzinfo=timezone.utc)
            existing = db.scalar(select(Fixture).where(
                Fixture.season_id == season.id,
                Fixture.home_team_id == home.id,
                Fixture.away_team_id == away.id,
                Fixture.kickoff_at == kickoff,
            ))
            if existing:
                duplicate_existing += 1
                continue

            db.add(Fixture(
                season_id=season.id, home_team_id=home.id, away_team_id=away.id,
                kickoff_at=kickoff, status="finished",
                home_goals=item["home_goals"], away_goals=item["away_goals"],
            ))
            imported += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "status": "completed",
        "rows_received": len(rows),
        "imported": imported,
        "duplicates_skipped": duplicates + duplicate_existing,
        "invalid_rows": 0,
        "message": "CSV berhasil diproses",
    }
