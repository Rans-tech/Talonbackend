# TALON Tool Playbook (v1.0)

## Purpose
Defines how TALON agents use real-time tools safely and consistently without polluting KB doctrine.

---

## Agent Responsibilities

### Atlas (Planner)
- Uses tools to improve planning accuracy.
- Integrates results naturally into itinerary drafts.
- Never exposes tool names or failures to the user.

### Houston (Coordinator)
- Routes tool access to the appropriate agent.
- Synthesizes results into user-facing responses.
- Enforces commit and status semantics.

### Specialist Agents
- Cassandra: uses outputs for risk thresholds.
- Churchill: uses outputs for recovery options.
- Ledger: uses outputs for cost comparison.
- Scout: uses outputs for local alternatives.
- Verifier: validates tool-derived data before confirmation.

---

## Tool Usage Rules
1. Do not call tools without sufficient context (dates, location, travelers).
2. Prefer one high-confidence call over many speculative calls.
3. Never claim certainty from probabilistic data.

---

## Caching & Staleness
- Weather: refresh if older than 48h and trip is <14 days out.
- Drive time: refresh if trip is <7 days out.
- Attractions/restaurants: refresh only on user request or major itinerary change.

---

## Failure Handling
- Silent fallback to KB or general knowledge.
- No user-facing error messages.
- Houston may ask clarifying questions if confidence drops below threshold.

---

## Logging (Internal)
Log each tool call:
- tool_id
- timestamp
- agent
- success/failure
- downstream usage (planning, commit, recovery)

---

## Status Semantics Reminder
Tool output never upgrades an item to CONFIRMED.
Only user-provided proof validated by Verifier can do that.
