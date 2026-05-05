# Backend Optional

## 1. Tighten CORS if deployment scope expands

- Narrow `allow_origins=["*"]` when the service moves beyond local or dev use.
- Impact: this is a deployment-hardening step, not a current blocker.
