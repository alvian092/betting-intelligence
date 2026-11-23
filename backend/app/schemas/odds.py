from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class BookmakerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider_key: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("provider_key")
    @classmethod
    def clean_provider_key(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class OddsQuoteIn(BaseModel):
    fixture_id: int = Field(ge=1)
    bookmaker_id: int = Field(ge=1)
    market: Literal["1x2", "totals", "asian_handicap", "btts", "correct_score", "team_total", "other"]
    selection: str = Field(min_length=1, max_length=80)
    line: Decimal | None = Field(default=None, ge=Decimal("-1000"), le=Decimal("1000"))
    decimal_odds: Decimal = Field(gt=Decimal("1"), le=Decimal("1000"), max_digits=10, decimal_places=4)
    captured_at: datetime
    quote_type: Literal["opening", "current", "closing", "live"]
    source: Literal["manual", "api"] = "manual"
    source_ref: str | None = Field(default=None, max_length=255)

    @field_validator("selection")
    @classmethod
    def clean_selection(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at wajib menyertakan timezone, contoh +07:00 atau Z")
        return value

    @model_validator(mode="after")
    def validate_market_line(self):
        if self.market in {"totals", "asian_handicap", "team_total"} and self.line is None:
            raise ValueError("Market totals, asian_handicap, dan team_total wajib memiliki line")
        if self.market in {"1x2", "btts", "correct_score"} and self.line is not None:
            raise ValueError("Market ini tidak menggunakan line")
        return self
