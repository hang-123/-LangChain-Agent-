# Project-Specific Rules (for Claude Code)

## 1. Source of Truth
- Before implementing any feature, **read the relevant spec files** under `spec/`.
- Treat `spec/` as the definitive product requirement source unless the user explicitly tells you otherwise.
- If a spec conflicts with existing code, **surface the conflict** in plain language before making broad changes.
- Do not silently "interpret around" missing or contradictory requirements. Ask for clarification.

## 2. Use of Skills
- If a repository skill (e.g., `superpower skills`) is present and relevant, use it to:
  - Summarize requirements from `spec/`.
  - Derive task breakdowns.
  - Generate implementation / review checklists.
- Skills support the workflow; they never override explicit spec requirements or user instructions.

## 3. Multi-Agent Task Splitting
For feature work that naturally splits into frontend and backend concerns, **prefer an explicit staged workflow** over one monolithic implementation pass.

Recommended order:
1. Read `spec/` and summarize the scope.
2. Split work into frontend and backend tasks.
3. Use separate subagents for frontend and backend implementation when parallelization is helpful.
4. After implementation, use separate reviewer subagents for frontend and backend review.
5. Return a single merged summary in the main thread.

**Do not spawn subagents unless**:
- The user explicitly asks for them, or
- The task clearly benefits from parallel work (e.g., non‑overlapping file sets).

> In Claude Code, you can spawn a subagent using `/task` (if a custom agent is configured in `.claude/agents/`) or by launching a fresh Claude Code process with a focused prompt. When in doubt, prefer a single‑threaded approach.

## 4. Frontend / Backend Boundaries
When using separate implementation subagents, enforce these boundaries:

### `frontend-implementer`
- Owns UI, page behavior, client‑side state, component composition, and frontend integration.
- Should avoid changing backend business logic, persistence logic, or data schemas unless explicitly requested.

### `backend-implementer`
- Owns API behavior, service logic, validation, persistence, and backend tests.
- Should avoid changing frontend UI or presentation concerns unless explicitly requested.

**Keep ownership boundaries explicit.** If a change crosses both sides, call that out before editing broadly.

## 5. Reviewer Agent Rules
Reviewer subagents are **read‑focused** and should not act like implementers.

### `frontend-reviewer`
Review for:
- correctness against spec
- UX/state edge cases
- error handling
- consistency with design system (if any)
- missing tests
- maintainability

### `backend-reviewer`
Review for:
- correctness against spec
- input validation
- contract / API consistency
- security concerns (injection, auth, data exposure)
- regression risk
- missing tests

### Default reviewer output format
Use this structure in the review summary:

- **Must fix** (blocking issues)
- **Should fix** (important but not blocking)
- **Optional improvement** (nice to have)

**Reviewers must not silently rewrite code** unless the user explicitly asks for a fix pass after the review.

## 6. Main Thread Behavior in Multi‑Agent Runs
In multi‑agent workflows, the **main thread acts as coordinator**.

The main thread should:
- Keep a short, actionable plan.
- Assign bounded work to subagents.
- Avoid flooding the main context with intermediate logs.
- Collect final outcomes, changed files, validation results, and risks.

The main thread must **not** mix implementation, review, and speculative redesign in one pass.

## 7. Validation Expectations
Each implementation agent should run the **narrowest relevant checks** for its own scope first.

Prefer:
- Targeted frontend tests for frontend changes.
- Targeted backend tests for backend changes.
- Broader checks (e.g., full integration suite) only when justified by scope or repo rules.

**Do not claim success without evidence.** If an important check was not run, say so explicitly.

## 8. Diff Discipline for Parallel Work
When multiple agents are involved:
- Prefer small, non‑overlapping diffs.
- Avoid touching the same files unless absolutely necessary.
- Avoid opportunistic cleanup (refactoring unrelated code).
- Explain any larger‑than‑local change before making it.

Parallelism is useful, but **reviewability is more important than concurrency**.

---

*These rules are a direct port of the original Codex project memory. They are enforced by Claude Code's built‑in instruction‑following. No special plugin required.*