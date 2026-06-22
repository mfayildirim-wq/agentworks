"""Modellpreise in USD pro 1M Tokens (Stand 2026)."""

from __future__ import annotations

_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-3-5-sonnet-latest": (3.0, 15.0),
    "claude-3-5-haiku-latest": (1.0, 5.0),
    # Lokale Ollama-Modelle: kostenlos
    "qwen2.5:3b": (0.0, 0.0),
    "llama3.2-vision:latest": (0.0, 0.0),
}

_DEFAULT = _PRICES["claude-sonnet-4-6"]


def price_for(model: str) -> tuple[float, float]:
    """Returns (input_per_million, output_per_million) USD."""
    return _PRICES.get(model, _DEFAULT)


def cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = price_for(model)
    return (tokens_in / 1_000_000) * pin + (tokens_out / 1_000_000) * pout
