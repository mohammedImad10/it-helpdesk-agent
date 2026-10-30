# Evaluation scorecard

| Suite | Cases | Passed | Average latency | P95 latency |
|---|---:|---:|---:|---:|
| Supplied Scenario 2 | 10 | 10 | 0.97 s | 1.38 s |
| Project-owned | 11 | 11 | 0.88 s | 1.23 s |

Both suites passed against the FastAPI contract and simulated Helpdesk API on 2026-10-31.
Detailed results are in `scorecard.supplied.md` and `scorecard.owned.md`; the project-owned
suite is in `cases.owned.jsonl`.

## Failure fixed

The initial `NX-403` path returned a generic review-required response. It now provides
KB-002/KB-007-grounded steps and only prepares a ticket after explicit escalation. A regression
test covers that behavior.

## Two-turn unknown escalation

The owned suite now includes CRM-1150: the employee confirms escalation in a second turn,
approves the stored draft, and the simulator confirms exactly one `other` ticket with no KB
references.
