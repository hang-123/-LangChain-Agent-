# Backend Optional

## 1. Consolidate more legacy coexistence code

- Current state:
  `api/main.py`, `api/core/graph.py`, and adjacent compatibility layers still carry both legacy and current paths.
- Risk:
  This is not breaking today, but it increases maintenance cost and makes future workflow changes harder to reason about.

## 2. Tighten CORS if deployment scope expands

- Current state:
  `allow_origins=["*"]` is still fine for local/dev.
- Risk:
  This becomes a deployment-hardening task once the service is exposed outside trusted environments.

