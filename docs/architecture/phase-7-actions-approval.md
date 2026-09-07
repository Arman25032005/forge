# Phase 7 — Actions + Approval

## Scope delivered
- **`Action` model** (`app/models/action.py`): tenant-scoped, optionally
  tied to the `Decision` it came from, with `action_type`, `parameters`,
  `status` (`proposed` → `approved`/`rejected` → `executed`/`failed`),
  `proposed_by`/`approved_by` (both real user IDs, not just role labels),
  `executed_at`, and `result`.
- **Three action types** (`app/services/action_types.py`):
  `flag_customer_at_risk` and `create_support_ticket` have real,
  verifiable side effects against this organization's own data (there is
  no external CRM/email/Slack integration in this codebase to execute
  against honestly, so those two are the only side effects that exist).
  `manual_task` deliberately has no automated side effect — many of Phase
  6's `recommended_actions` are things only a human can do ("call the
  customer"), and executing this type just records that a human marked it
  done rather than pretending the system performed an action it can't.
- **Maker-checker approval, enforced in code**: `approve_action` rejects
  approving your own proposed action (`ActionPermissionError`), regardless
  of role — an ADMIN can propose and a different ADMIN can approve, but
  the same user can't do both. This is checked against the actual
  `proposed_by` user id, not just against role, so two users with the
  same role still can't self-approve.
- **State machine enforced in code**: `approve`/`reject` only accept an
  action in `proposed` status; `execute` only accepts `approved`. Each
  invalid transition raises `ActionStateError` (400), not a silent no-op
  or a corrupted state.
- **API** (`app/api/actions.py`): `POST /actions` (propose, gated by
  `action.propose`), `POST /actions/{id}/approve`, `POST
  /actions/{id}/reject`, `POST /actions/{id}/execute` (all three gated by
  `action.execute`), `GET /actions`, `GET /actions/{id}` (gated by
  `action.propose`, the broader of the two).

## What was actually tested, and how
99 tests in `apps/api/tests/` (up from 84 after Phase 6), all passing
against real SQLite through the actual FastAPI app / action services —
not mocks of our own code.

| Check | Test(s) | Result |
|---|---|---|
| `flag_customer_at_risk` actually updates the customer row, tenant-scoped | `test_flag_customer_at_risk_updates_status`, `test_flag_customer_at_risk_is_tenant_scoped` | pass |
| `create_support_ticket` actually creates a real `SupportTicket` row | `test_create_support_ticket_creates_real_row` | pass |
| `manual_task` has no side effect and says so | `test_manual_task_has_no_side_effect` | pass |
| Full propose → approve → execute lifecycle, with a real side effect | `test_full_propose_approve_execute_lifecycle` | pass |
| A user cannot approve their own proposed action | `test_cannot_approve_own_proposal` | pass |
| Invalid state transitions rejected (execute-before-approve, approve-after-reject) | `test_cannot_execute_unapproved_action`, `test_cannot_approve_already_rejected_action` | pass |
| A failing execution (e.g. customer no longer exists) records the error and marks `failed` rather than crashing | `test_failed_execution_records_error_without_crashing` | pass |
| ANALYST (has `action.propose`, not `action.execute`) can propose but not approve | `test_analyst_can_propose_but_not_approve` | pass |
| VIEWER cannot propose actions at all | `test_viewer_cannot_propose_actions` | pass |
| Unknown action type rejected (400) | `test_unknown_action_type_rejected` | pass |
| Cross-user maker-checker over HTTP (ANALYST proposes, OPERATOR approves+executes) | `test_operator_can_propose_approve_and_execute_a_different_users_action` | pass |
| Actions are tenant-isolated | `test_actions_are_tenant_isolated` | pass |

Beyond the pytest suite, the full lifecycle was exercised manually against
a real running server and real generated data: an ANALYST proposed
`flag_customer_at_risk` for a real customer (looked up via `/data/query`,
not fabricated), attempting to approve as the proposer was rejected
(missing `action.execute` in this case, since the proposer's role lacked
it), an OPERATOR approved and executed it, and a fresh `/data/query`
against the same customer confirmed `status = 'at_risk'` — the side
effect was independently re-verified, not just trusted from the
`execute` response.

`ruff check`, `ruff format --check`, and `mypy app` are all clean. The
`actions` migration was applied and rolled back against a real SQLite
file, chained on top of the Phase 6 migration.

## What was NOT tested (honest limitations)
- **Only two of three action types have a real side effect.** There is no
  external system (CRM, email, ticketing SaaS, Slack) in this codebase to
  integrate with, so "action execution" is necessarily scoped to this
  app's own database. A production deployment would need real connector
  implementations behind the same `ActionTypeSpec` interface — the
  interface is designed for that (an `execute` function taking
  `(db, organization_id, parameters)` and returning a result dict), but no
  such connector exists yet.
- **No automated linkage from a Decision's `recommended_actions` (plain
  strings, from Phase 6) to a proposable `Action`.** Turning "reach out to
  at-risk customers" into a concrete `create_support_ticket` proposal is
  currently a manual step (a human, or a future agent, calls `POST
  /actions` themselves); there's no automatic string-to-action-type
  mapping.
- **No audit-log entry is written for action proposal/approval/execution**
  the way Phase 2's auth events are. Actions have their own status/timestamp
  trail on the row itself, but that's not the same as an append-only,
  cross-cutting audit record — the same gap the Phase 2 report flagged for
  the audit system generally (no rate limiting/revocation either).
- **No rollback/compensation** if an executed action turns out to be
  wrong — reversing a `flag_customer_at_risk` requires manually proposing
  and executing the opposite action.

## Gate status
Propose → approve/reject → execute is implemented end-to-end with real
side effects for the two action types that can honestly have one,
maker-checker approval enforced in code against real user identities (not
just role labels), and full RBAC/tenant-isolation coverage — all verified
by tests and by a manual run against real generated data with an
independent re-check of the resulting side effect. The gaps above are
scope boundaries (no external system integrations exist to execute
against) and a missing audit trail for this specific action-approval
flow, not unbuilt core functionality.
