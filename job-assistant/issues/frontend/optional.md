# Frontend Optional

## 1. Reduce repeated card shell markup

- Refactor the repeated artifact-card shell in `web/src/components/ReportView.tsx`.
- Impact: this would improve maintainability, but it is not required for correctness.

## 2. Move workflow summary to a backend-owned artifact

- `workflowSummary` is still inferred client-side from returned artifacts.
- Impact: this is acceptable for now, but a backend-owned workflow summary would reduce drift if workflow semantics change later.

## 3. Refresh `baseline-browser-mapping`

- `npm test`, `npm run build`, and `npm run lint` now emit a stale-data warning for `baseline-browser-mapping`.
- Impact: no functional breakage today, but the warning adds noise to verification runs.
