# Billing

**Status:** außerhalb des aktuellen Plans (Phase 4).

Aktueller Zustand:

- `agents.price_per_run` ist nur UI-Anzeige; es findet keine echte Buchung statt.
- Kosten in `work_runs.total_cost` reflektieren reale LLM-Token-Kosten (USD), nicht den
  vom Owner gesetzten Mietpreis.

Phase 4 (separates Spec) wird:

- Stripe-Customer pro `user`.
- Wallet/Credits oder direkte Belastung pro Run.
- Owner-Revenue-Share (z.B. 70/30).
- Rechnungen, Steuern, Compliance.
- AGB / DPA.
