# Feedback from prediction outcomes

Selection feedback v1 uses frozen, pre-match choices with verified scores and a recorded settlement time. It compares wins **and** losses over 180 days. Pending, void, retroactive, duplicate, inconsistent and unobserved records do not train the policy. Prior editorial results without observation times are progressively reverified (up to ten historical boards each refresh); published choices remain unchanged.

The editorial board learns from its own shared history. Authenticated match/ticket analyses can additionally use only the caller's saved selections and matching analysis snapshots. Other accounts are never pooled or exposed. Training is separated by model version, market, probability band and, when available, competition. At least 30 distinct fixtures and an overconfidence gap beyond an approximate sampling margin are required. The ranking penalty shrinks with sample size, is capped at ten points and never changes model probabilities. Overlapping global and competition penalties are not added together. A model version without sufficient evidence has no adjustment.

Buteurs use a separate availability comparison, separated by scorer model and men's/women's competition category. Both groups need 30 distinct events; only explicit individual goals and settlement observations count. The ranking multiplier stays between 0.8 and 1. No player scoring percentages are invented. Private scorer selections currently do not train this scorer policy.

`GET /api/daily-opinion/learning` reports eligible observations, excluded records, penalties and recent defeats. Authenticated responses include only that user's own data in addition to the shared board. The compact “Bilan et amélioration de l’IA” control lives in the daily opinion view.

This is bounded feedback on future selection ranking, not neural-model retraining. It does not identify the causal reason for a defeat. Selection bias and correlated markets limit interpretation. There is no demonstrated out-of-sample improvement yet; real subsequent results must establish whether the policy helps. The historical win rate and probabilities are never rewritten.

## Audit in this change

- Baseline: 373 Python tests pass.
- The latest GitHub failure was the isolated personnel browser fixture omitting `cleanAnalysisText`, which production loads from index.html. The fixture now loads the production helper before testing the personnel refresh.
- New regression tests cover repeated errors, minimum sample sizes, model/band separation, timestamps, invalid outcomes, duplicates, immutable published choices, private ownership and scorer feedback.

- All 381 Python tests pass after implementation. Browser-free JavaScript checks cover tickets, bankroll, calendars, scorer history, billing, competition selection and compact navigation. A late CSS visibility rule also ensures paginated hidden match cards stay hidden. Full Chromium execution is blocked by local socket restrictions; the GitHub browser run is used for integration validation.
