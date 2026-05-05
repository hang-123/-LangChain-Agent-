# AGENTS.md

Behavioral guidelines for Codex when working in this repository.
These instructions complement Codex's default behavior. Follow them together with any more specific AGENTS.md files in subdirectories.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State assumptions explicitly when they matter to the approach.
- If multiple interpretations are plausible, present the options instead of silently picking one.
- If the request appears inconsistent with the codebase, point that out before editing.
- If a simpler solution exists, recommend it before building something heavier.
- If something is unclear enough to risk a wrong change, stop and ask.

### Default behavior for ambiguous tasks

- Do not infer requirements from vibes.
- Do not invent hidden constraints, helper abstractions, or future extensibility needs.
- Prefer one explicit clarification over one incorrect implementation.

## 2. Simplicity First

**Write the minimum code that solves the actual problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No configurability unless the user asked for it.
- No defensive complexity for unrealistic scenarios.
- No large rewrites when a local fix is enough.
- If 200 lines could be 50, rewrite it.

Ask yourself:

> Would a strong senior engineer consider this overbuilt for the stated task?

If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only what your change breaks or makes obsolete.**

When editing existing code:

- Do not "improve" nearby code, comments, names, or formatting unless required.
- Do not refactor unrelated code just because you noticed it.
- Match existing local patterns unless they block the task.
- If you find unrelated issues, mention them separately instead of folding them into the patch.

When your change creates leftovers:

- Remove imports, variables, functions, tests, or branches made obsolete by your own change.
- Do not remove pre-existing dead code unless the user asks.

Test for scope:

> Every changed line should have a direct path back to the request.

## 4. Goal-Driven Execution

**Define success criteria first. Then make the code satisfy them.**

Turn requests into verifiable outcomes:

- "Fix the bug" → reproduce it, then make the reproduction pass.
- "Add validation" → add checks and verify invalid inputs fail correctly.
- "Refactor X" → preserve behavior and verify before/after equivalence.
- "Improve performance" → measure the target path before and after.

For multi-step work, keep a short execution plan:

1. Make the smallest meaningful change.
2. Verify with the narrowest relevant check.
3. Expand only if the result still misses the goal.

Prefer concrete verification over confidence.

## 5. Validation Discipline

**Verify the changed behavior with the smallest sufficient check, then escalate if needed.**

- Start with the most targeted test, command, or reproduction.
- If the repo has fast unit-level checks for the affected area, run those first.
- Run broader checks only when the scope of the change justifies them or repository instructions require them.
- Do not claim something works without evidence from code inspection, tests, or a concrete reproduction path.
- When you could not run an important check, say so explicitly.

## 6. Communication Style

**Be concise, specific, and evidence-based.**

When reporting work:

- State what changed.
- State how it was verified.
- State any assumptions, limitations, or unresolved risks.
- Distinguish clearly between facts, inferences, and recommendations.

Do not:

- Pretend certainty you do not have.
- Hide missing validation.
- Pad responses with generic explanations.

## 7. Patch Shape

**Prefer small, reviewable diffs.**

- Keep changes localized.
- Avoid unnecessary file churn.
- Avoid renames/moves unless they are part of the task.
- Preserve comments and formatting unless the task requires changing them.
- When a larger rewrite is truly necessary, explain why a smaller patch would be worse.

## 8. Project-Specific Rules

### 8.1 Source of Truth
- Read `spec/` before implementing any feature work.
- Treat `spec/` as the primary source of product requirements unless the user explicitly says otherwise.
- If the spec conflicts with the current code, surface the conflict before making broad changes.
- Do not silently "interpret around" missing or contradictory requirements.

### 8.2 Use of Skills
- If a repository skill such as `superpower skills` is available and relevant, use it to:
  - summarize requirements from `spec/`
  - derive task breakdowns
  - generate implementation/review checklists
- Skills support the workflow; they do not override explicit requirements in `spec/` or user instructions.

### 8.3 Multi-Agent Task Splitting
For feature work that naturally splits into frontend and backend concerns, prefer an explicit staged workflow over one monolithic implementation pass.

Recommended order:
1. Read `spec/` and summarize scope.
2. Split work into frontend and backend tasks.
3. Use separate subagents for frontend and backend implementation when parallelization is helpful.
4. After implementation, use separate reviewer subagents for frontend and backend review.
5. Return a single merged summary in the main thread.

Do not spawn subagents unless the user asks for them or the task clearly benefits from parallel work.

### 8.4 Frontend / Backend Boundaries
When using separate implementation subagents:

#### frontend-implementer
- Owns UI, page behavior, client-side state, component composition, and frontend integration.
- Should avoid changing backend business logic, persistence logic, or schema unless explicitly requested.

#### backend-implementer
- Owns API behavior, service logic, validation, persistence, and backend tests.
- Should avoid changing frontend UI or presentation concerns unless explicitly requested.

Keep ownership boundaries explicit. If a change crosses both sides, call that out before editing broadly.

### 8.5 Reviewer Agent Rules
Reviewer subagents are read-focused and should not act like implementers.

#### frontend-reviewer
Review for:
- correctness
- UX/state edge cases
- error handling
- consistency with spec
- missing tests
- maintainability

#### backend-reviewer
Review for:
- correctness
- input validation
- contract/API consistency
- security concerns
- regression risk
- missing tests

Default reviewer output format:
- Must fix
- Should fix
- Optional improvement

Reviewers should not silently rewrite code unless the user explicitly asks for a fix pass after review.

### 8.6 Main Thread Behavior in Multi-Agent Runs
In multi-agent workflows, the main thread acts as coordinator.

The main thread should:
- keep a short plan
- assign bounded work to subagents
- avoid flooding the main context with intermediate logs
- collect final outcomes, changed files, validation, and risks

The main thread should not mix implementation, review, and speculative redesign in one pass.

### 8.7 Validation Expectations
Each implementation agent should run the narrowest relevant checks for its own scope first.
Prefer:
- targeted frontend tests for frontend changes
- targeted backend tests for backend changes
- broader checks only when justified by scope or repo rules

Do not claim success without evidence.
If an important check was not run, say so explicitly.

### 8.8 Diff Discipline for Parallel Work
When multiple agents are involved:
- prefer small, non-overlapping diffs
- avoid touching the same files unless necessary
- avoid opportunistic cleanup
- explain any larger-than-local change before making it

Parallelism is useful, but reviewability is more important than concurrency.