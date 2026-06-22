from __future__ import annotations

from pydantic import BaseModel, Field


class McpServerOut(BaseModel):
    server_id: str
    name: str
    description: str
    transport: str
    url: str
    requires_credential: bool
    enabled: bool
    auth_header: str = "Authorization"
    auth_value_template: str = "Bearer {secret}"
    secret_label: str = "Token / API-Key"


class McpServerCreate(BaseModel):
    server_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=512)
    transport: str = Field(default="streamable_http", max_length=20)
    url: str = Field(min_length=1, max_length=512)
    requires_credential: bool = False
    auth_header: str = Field(default="Authorization", max_length=80)
    auth_value_template: str = Field(default="Bearer {secret}", max_length=200)
    secret_label: str = Field(default="Token / API-Key", max_length=120)


class McpServerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    transport: str | None = None
    url: str | None = None
    requires_credential: bool | None = None
    enabled: bool | None = None
    auth_header: str | None = None
    auth_value_template: str | None = None
    secret_label: str | None = None
