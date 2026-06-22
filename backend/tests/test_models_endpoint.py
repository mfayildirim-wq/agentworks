async def test_list_models_returns_billable_models(client):
    res = await client.get("/models")
    assert res.status_code == 200
    items = res.json()
    values = [m["value"] for m in items]
    # Claude/OpenAI aus der Preis-Tabelle, kein Ollama.
    assert "claude-haiku-4-5" in values
    assert "gpt-4o" in values
    assert all("qwen" not in v for v in values)
    haiku = next(m for m in items if m["value"] == "claude-haiku-4-5")
    assert haiku["label"] == "Claude Haiku 4.5"
    assert haiku["group"] == "Anthropic"
