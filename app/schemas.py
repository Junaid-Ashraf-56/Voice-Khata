"""Pydantic models. Everything the model returns is validated through these."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Kind = Literal["udhaar", "payment"]


class AddEntryArgs(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0)
    kind: Kind
    note: Optional[str] = Field(default=None, max_length=200)

    @field_validator("customer_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("customer_name is empty")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def _no_bool(cls, v):
        # pydantic's lax mode would turn True into 1
        if isinstance(v, bool):
            raise ValueError("amount must be an integer")
        return v


class GetBalanceArgs(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)

    @field_validator("customer_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("customer_name is empty")
        return v


class Extraction(BaseModel):
    """Validated result of stage 2, before the customer name is resolved."""
    action: Literal["add_entry", "get_balance"]
    customer_name: str
    amount: Optional[int] = None
    kind: Optional[Kind] = None
    note: Optional[str] = None


class Proposal(BaseModel):
    """What the user is asked to confirm. Held server-side until /api/confirm."""
    id: str
    transcript: str
    customer_name: str          # resolved: existing name, or the proposed new one
    is_new_customer: bool
    similar_names: list[str] = []   # near matches, shown as a hint, never auto-applied
    amount: int
    kind: Kind
    note: Optional[str] = None


class BalanceAnswer(BaseModel):
    customer_name: str
    found: bool
    balance: int = 0            # >0: customer owes the shopkeeper; <0: shopkeeper owes customer
    similar_names: list[str] = []


class ProcessResponse(BaseModel):
    transcript: str
    action: Literal["add_entry", "get_balance"]
    proposal: Optional[Proposal] = None
    balance: Optional[BalanceAnswer] = None


class ConfirmRequest(BaseModel):
    proposal_id: str


class ConfirmResponse(BaseModel):
    entry_id: int
    customer_name: str
    balance: int
