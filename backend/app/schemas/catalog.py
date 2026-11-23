from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CountryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=3)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class LeagueIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    country_id: int | None = Field(default=None, ge=1)
    external_id: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class SeasonIn(BaseModel):
    league_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=40)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date tidak boleh sebelum start_date")
        return self


class TeamIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    external_id: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("country_code")
    @classmethod
    def clean_country_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class FixtureIn(BaseModel):
    season_id: int = Field(ge=1)
    home_team_id: int = Field(ge=1)
    away_team_id: int = Field(ge=1)
    kickoff_at: datetime
    status: str = "scheduled"
    home_goals: int | None = Field(default=None, ge=0)
    away_goals: int | None = Field(default=None, ge=0)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"scheduled", "live", "finished", "postponed", "cancelled"}
        if value not in allowed:
            raise ValueError("status harus scheduled, live, finished, postponed, atau cancelled")
        return value

    @model_validator(mode="after")
    def valid_fixture(self):
        if self.home_team_id == self.away_team_id:
            raise ValueError("Tim kandang dan tandang harus berbeda")
        if (self.home_goals is None) != (self.away_goals is None):
            raise ValueError("Skor kandang dan tandang harus diisi berpasangan")
        if self.status == "finished" and self.home_goals is None:
            raise ValueError("Pertandingan finished wajib memiliki skor")
        return self


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
