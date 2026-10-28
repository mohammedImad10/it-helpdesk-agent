# Evaluation scorecard

| Suite | Cases | Passed | Average latency | P95 latency |
|---|---:|---:|---:|---:|
| Supplied Scenario 2 | 10 | 10 | 1.06 s | 1.48 s |
| Project-owned | 10 | 10 | 0.96 s | 1.32 s |

All cases passed against the FastAPI contract and simulated Helpdesk API. The project-owned
suite is in `evals/cases.owned.jsonl`.

## Failure fixed

The initial `NX-403` path returned a generic review-required response. It now provides
KB-002/KB-007-grounded steps and only prepares a ticket after explicit escalation. A regression
test covers that behavior.
