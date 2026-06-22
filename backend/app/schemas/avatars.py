from __future__ import annotations

from pydantic import BaseModel, Field


class AvatarGenerateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    prompt: str = ""
    # Optionaler Freitext: beschreibt direkt, was der Avatar zeigen soll. Gesetzt →
    # Beschreibungsstufe wird übersprungen und dieser Text steuert das Bild.
    hint: str = Field(default="", max_length=500)
    # Gewählter Stil (siehe avatar_styles); leer/unbekannt → Default-Stil.
    style: str = Field(default="", max_length=80)


class AvatarGenerateResponse(BaseModel):
    url: str


class AvatarStyleOut(BaseModel):
    id: str
    label: str
    group: str
