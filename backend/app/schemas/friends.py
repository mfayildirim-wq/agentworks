from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class FriendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str
    avatar_url: str | None = None

class UserSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    avatar_url: str | None = None

class FriendRequestOut(BaseModel):
    id: UUID            # friendship id
    requester_id: UUID
    name: str           # requester name
    avatar_url: str | None = None

class FriendRequestIn(BaseModel):
    email_or_name: str
