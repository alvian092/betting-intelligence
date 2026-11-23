from pydantic import BaseModel, Field, field_validator, model_validator


class OddsSelectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    model_probability: float = Field(gt=0, lt=1)
    decimal_odds: float = Field(gt=1, le=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class OddsValueIn(BaseModel):
    selections: list[OddsSelectionIn] = Field(min_length=2, max_length=20)
    fractional_kelly: float = Field(default=0.25, gt=0, le=1)
    min_ev: float = Field(default=0.02, ge=0, lt=1)

    @model_validator(mode="after")
    def unique_names(self):
        names = [item.name for item in self.selections]
        if len(names) != len(set(names)):
            raise ValueError("Nama selection harus unik")
        return self
