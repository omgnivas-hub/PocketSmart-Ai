"""Pydantic request schemas (input validation)."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

MAX_BUDGET = 100_000_000  # ₹10 crore sanity cap


class RegisterUser(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class HomeBudgetInput(BaseModel):
    total_budget: float = Field(gt=0, le=MAX_BUDGET)
    num_lights: int = Field(default=0, ge=0, le=200)
    num_fans: int = Field(default=0, ge=0, le=100)
    num_furniture: int = Field(default=0, ge=0, le=200)
    num_dining_tables: int = Field(default=0, ge=0, le=50)
    has_living_room: bool = True
    has_kitchen: bool = True
    has_bedroom: bool = False
    additional_requirements: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _need_one_item(self):
        if self.num_lights + self.num_fans + self.num_furniture + self.num_dining_tables == 0:
            raise ValueError("Enter a quantity for at least one item (lights, fans, furniture or dining tables)")
        return self


class PartyBudgetInput(BaseModel):
    total_budget: float = Field(gt=0, le=MAX_BUDGET)
    num_guests: int = Field(ge=1, le=5000)
    party_type: str = Field(default="birthday", min_length=2, max_length=40)
    venue_type: Optional[str] = Field(default=None, max_length=60)
    needs_catering: bool = True
    needs_decoration: bool = True
    needs_entertainment: bool = True
    additional_requirements: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _need_one_service(self):
        if not (self.needs_catering or self.needs_decoration or self.needs_entertainment):
            raise ValueError("Select at least one party need (catering, decoration or entertainment)")
        return self


class JewelryBudgetInput(BaseModel):
    total_budget: float = Field(gt=0, le=MAX_BUDGET)
    occasion: str = Field(min_length=2, max_length=60)
    preferences: Optional[str] = Field(default=None, max_length=500)
