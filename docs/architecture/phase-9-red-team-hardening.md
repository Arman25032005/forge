# Phase 9 — Red-Team Hardening

## Scope
This phase closes gaps explicitly flagged as deferred in earlier phase
docs, plus two issues found by auditing the phases built since: Phase 2
flagged "no refresh tokens / logout / revocation" and "rate limiting on
login/register is not implemented," both "to be picked up ... in Phase 9
(Red Team + Hardening)." This phase implements both, fixes a real
cross-tenant reference gap found while auditing Phase 7's `Action` model,
hardens the two LLM-facing system prompts against prompt injection via
tool output, and fixes a real datetime-comparison bug found while testing
the refresh-token expiry path.

## Scope delivered
- **Rate limiting** (`app/services/rate_limit.py`): a `RateLimiter`
  protocol with a fixed-window `InMemoryRateLimiter` (correct, tested,
  single-process) and a `RedisRateLimiter` (real INCR+EXPIRE
  implementation for multi-instance deployments, not exercised against a
  live Redis here — no Docker in this environment, same limitation as
  every other Redis-touching code path since Phase 1).
  `POST /auth/login` is rate-limited **per account** (`org_slug:email`,
  checked before password verification, so failed attempts against one
  account are throttled regardless of which IP they come from);
  `POST /auth/register` is rate-limited per client IP (there's no account
  identity yet at that point). Both return 429, not a silent block.
- **Refresh tokens, logout, and rotation** (`app/services/refresh_tokens.py`,
  `app/models/refresh_token.py`): `POST /auth/login` now returns both an
  access token and a refresh token. `POST /auth/refresh` validates the
  refresh token (not expired, not revoked, user still active), issues a
  new access token, and **rotates** the refresh token — the old one is
  revoked in the same call, so a refresh token can only ever be used
  once, live or stolen. `POST /auth/logout` revokes a refresh token
  outright. Only a SHA-256 hash of the token is ever stored, mirroring
  how passwords are handled — a leaked `refresh_tokens` row is not itself
  a usable credential.
- **Cross-tenant reference fix (real bug found and fixed)**: `Action.decision_id`
  (added in Phase 7) was never checked against the caller's own
  organization — a user could propose an action citing another tenant's
  `Decision` id, since the FK constraint only requires the row to exist
  *somewhere*, not in the same tenant. `propose_action` now looks up the
  referenced decision scoped to the caller's `organization_id` and
  rejects the request (400) if it isn't found there.
- **Prompt-injection hardening**: both LLM-facing system prompts
  (`app/services/llm.py`, `app/services/decision_synthesis.py`) now
  explicitly instruct the model that tool/step output is untrusted data
  from the tenant's own database and documents, never instructions to
  follow — a real, concrete mitigation for a poisoned document or ticket
  subject line reading, e.g., "ignore previous instructions." Each prompt
  is now a named module constant (`SYSTEM_PROMPT`) specifically so its
  content is checkable without a network call.
- **A second real bug found and fixed while testing the above**:
  comparing a SQLite-read `expires_at` (naive, despite being declared
  `DateTime(timezone=True)` — SQLite doesn't round-trip tzinfo the way
  Postgres does) against `datetime.now(UTC)` (aware) raised `TypeError`,
  not a clean expiry check. This is exactly the same *class* of bug as
  Phase 3's UUID-dialect bug: a SQLite/Postgres behavioral difference
  that only surfaces when you actually exercise the code path, which the
  expired-token test did. Fixed by normalizing naive timestamps to UTC
  before comparing (`_as_aware_utc` in `refresh_tokens.py`).

## What was actually tested, and how
118 tests in `apps/api/tests/` (up from 104 after Phase 8), all passing
against real SQLite through the actual FastAPI app — not mocks.

| Check | Test(s) | Result |
|---|---|---|
| Login is rate-limited after repeated attempts, scoped per-account (a blocked account doesn't block a different account) | `test_rate_limiting.py` (2 tests) | pass |
| Registration is rate-limited after repeated attempts | `test_register_is_rate_limited_after_repeated_attempts` | pass |
| Login returns a refresh token | `test_login_returns_a_refresh_token` | pass |
| Refresh issues a new access token and rotates the refresh token | `test_refresh_issues_a_new_access_token` | pass |
| A rotated (already-used) refresh token cannot be replayed | `test_reusing_a_rotated_refresh_token_fails` | pass |
| Logout revokes the refresh token; logging out an unknown token still returns 204 (doesn't leak whether it existed) | `test_logout_revokes_the_refresh_token`, `test_logout_with_unknown_token_still_returns_204` | pass |
| An expired refresh token is rejected | `test_expired_refresh_token_is_rejected` | pass |
| A garbage refresh token is rejected | `test_refresh_with_garbage_token_is_rejected` | pass |
| An action cannot reference another tenant's decision; can reference its own | `test_actions_cross_tenant_reference.py` (2 tests) | pass |
| Both LLM system prompts actually contain the untrusted-data framing | `test_prompt_injection_hardening.py` (2 tests) | pass |

Beyond pytest, the full auth hardening surface was manually exercised
against a real running server: login → refresh → replay-the-old-token
(401) → logout-with-the-new-token (204) → use-the-logged-out-token (401),
and 7 rapid login attempts against one account correctly returned 401 for
the attempts within budget and 429 once the account's window was
exhausted (accounting for a prior successful login already having
consumed one slot — the count matched exactly, not approximately). The
cross-tenant `decision_id` fix was also confirmed live: an OPERATOR in
one organization referencing a random decision id got a 400 explaining
no such decision exists in their tenant.

`ruff check`, `ruff format --check`, and `mypy app` are all clean. The
`refresh_tokens` migration was applied and rolled back against a real
SQLite file, chained on top of the Phase 8 migration point (Phase 8 added
no migration of its own — Phase 7's `actions` migration is the true
parent).

## What was NOT tested (honest limitations)
- **`RedisRateLimiter` has never run against a live Redis instance** —
  same root cause as every other Redis-dependent path in this codebase
  (no Docker here). It's a straightforward INCR+EXPIRE implementation and
  is believed correct, but "believed correct" is exactly the phrase this
  project's honesty policy exists to flag rather than launder into "done."
- **In-memory rate limiting doesn't survive a process restart or work
  across multiple instances** — by design, and documented as such, but
  worth restating: a production multi-instance deployment must set
  `FORGE_RATE_LIMIT_BACKEND=redis` or the limit is trivially bypassed by
  hitting a different instance.
- **No IP-based limiting on login**, only per-account — a distributed
  attacker spraying many different accounts from many IPs isn't
  throttled by this phase's login limiter (each account gets its own
  budget). Register's IP-based limiting doesn't have this gap since there
  is no per-account identity to key on at that point.
- **Prompt-injection hardening is unverified against a live model** — the
  system prompts now say the right thing, but whether Claude actually
  resists a crafted "ignore previous instructions" string embedded in a
  document has not been tested, because there is still no
  `FORGE_ANTHROPIC_API_KEY` in this environment. This is inherited from,
  not new to, this phase.
- **No account lockout, no CAPTCHA, no anomaly detection** — rate
  limiting slows brute force, it doesn't stop a patient attacker willing
  to wait out the window repeatedly.
- **This was a targeted audit of gaps already named plus a pass over
  Phases 3–8's newer surface area (the `Action`/`Decision` relationship),
  not an exhaustive red-team exercise** — no fuzzing, no dependency
  vulnerability scan, no review of the frontend (`apps/web`), which this
  phase did not touch.

## Gate status
Both named Phase 2 gaps (rate limiting, refresh/logout/revocation) are
closed with real, tested implementations. One previously-unflagged
cross-tenant reference bug and one SQLite-specific datetime bug were
found and fixed during this phase's own testing, in the same spirit as
bugs surfaced in Phases 3 and 4 — found by actually exercising the code,
not by inspection alone. Prompt-injection mitigation is real but its
effectiveness against an actual model is unverified, consistent with
every other Claude-dependent gap already on record.
