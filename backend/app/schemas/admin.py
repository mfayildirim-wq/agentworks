from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str
    role: str
    topup_mode: str = "free"
    is_system_admin: bool = False
    balance_usd: float = 0

class SetRoleIn(BaseModel):
    role: Literal["", "admin"]   # ungültige Werte → 422 statt stillem No-Op

class SetTopupModeIn(BaseModel):
    mode: Literal["free", "real"]

class GrantCreditIn(BaseModel):
    amount_usd: float = Field(gt=0, le=1000)

class PublicationRequestOut(BaseModel):
    id: UUID
    title: str
    category: str
    owner_name: str
    created_at: datetime

class RejectIn(BaseModel):
    note: str = Field("", max_length=2000)
