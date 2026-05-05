# Issue Archive

This folder persists the latest known implementation and review issues for the Resume Tailor workstream.

## Structure

- `frontend/must-fix.md` - blocking UI and state issues.
- `frontend/should-fix.md` - correctness and resilience improvements for the UI.
- `frontend/optional.md` - low-priority polish items.
- `backend/must-fix.md` - blocking API and agent-contract issues.
- `backend/should-fix.md` - correctness and validation improvements for the backend.
- `backend/optional.md` - low-priority infrastructure polish.

## Notes

- The contents should be updated after each repair/review cycle.
- Remove resolved issues instead of marking them done inline.
- Add newly discovered issues to the smallest matching category file.
- Prefer moving issues down in severity as work lands, instead of rewriting the whole archive.
- Keep updates small and category-based so the archive stays easy to review.
