from agent_runtime.pricing import cost, price_for


def test_local_ollama_model_is_zero_cost():
    assert price_for("qwen2.5:3b") == (0.0, 0.0)
    assert cost("qwen2.5:3b", 1_000_000, 1_000_000) == 0.0


def test_unknown_model_still_defaults_to_sonnet():
    # Regression: nicht-lokale unbekannte Modelle behalten den Sonnet-Default
    assert price_for("irgendwas-fremdes") == (3.0, 15.0)
