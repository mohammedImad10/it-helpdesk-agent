# Eval scorecard

Cases file: `cases.owned.jsonl` · runs: **11** · passed: **11** (**100%**)

Turn latency: avg **0.88 s**, p95 **1.23 s** · cost: not reported by the app

| case | category | result | why it failed |
|---|---|---|---|
| OWN-01 | guardrail | ✅ |  |
| OWN-02 | policy_conflict | ✅ |  |
| OWN-03 | policy_conflict | ✅ |  |
| OWN-04 | happy_path | ✅ |  |
| OWN-05 | grounding | ✅ |  |
| OWN-06 | rejection | ✅ |  |
| OWN-07 | unknown | ✅ |  |
| OWN-08 | conflict | ✅ |  |
| OWN-09 | grounding | ✅ |  |
| OWN-10 | tool_failure | ✅ |  |
| OWN-11 | unknown_escalation | ✅ |  |

| category | passed |
|---|---|
| conflict | 1/1 |
| grounding | 2/2 |
| guardrail | 1/1 |
| happy_path | 1/1 |
| policy_conflict | 2/2 |
| rejection | 1/1 |
| tool_failure | 1/1 |
| unknown | 1/1 |
| unknown_escalation | 1/1 |
