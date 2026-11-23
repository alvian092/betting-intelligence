from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    code: Mapped[str | None] = mapped_column(String(3), unique=True, nullable=True)
    leagues: Mapped[list["League"]] = relationship(back_populates="country")


class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    country: Mapped[Country | None] = relationship(back_populates="leagues")
    seasons: Mapped[list["Season"]] = relationship(back_populates="league")
    __table_args__ = (UniqueConstraint("country_id", "name", name="uq_league_country_name"),)


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    league: Mapped[League] = relationship(back_populates="seasons")
    __table_args__ = (UniqueConstraint("league_id", "name", name="uq_season_league_name"),)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    country_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (
        UniqueConstraint("season_id", "home_team_id", "away_team_id", "kickoff_at", name="uq_fixture_identity"),
    )
