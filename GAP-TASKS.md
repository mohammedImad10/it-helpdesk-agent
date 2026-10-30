# Final Mini-Project Gap Tasks

This checklist is based on the Final Mini-Project and Scenario 2 review. Complete
the blocking items first, then rerun the verification commands in the relevant task.

## Blocking requirements

- [x] **Make the LangGraph roles control the workflow**
  - **Gap:** The Intake & Safety role can influence the topic, but the Resolution &
    Escalation decision is not used to select the user-visible result. Most outcomes
    are fixed branches in `app/workflow.py`.
  - **Done when:** Each role has a distinct, observable responsibility and its output
    affects routing or the response. Keep deterministic policy, approval, and
    validation checks in Python.
  - **Verify:** Add tests proving a resolution decision selects an answer,
    escalation, or ticket-draft path.

- [x] **Add real embedding-based retrieval**
  - **Gap:** Current retrieval is keyword and error-code matching only.
  - **Done when:** Ingestion creates embeddings through a real external API, stores
    vectors with chunk metadata, and retrieval combines exact error-code matching
    with semantic similarity. Keep deterministic precedence filtering after retrieval.
  - **Verify:** Re-ingest the KB and add cases where semantically equivalent wording
    retrieves the intended current source, including PDF-only content.

- [x] **Add structured application logging**
  - **Gap:** Responses include `tool_calls`, but tool calls and failures are not
    emitted as readable application logs.
  - **Done when:** Every MCP call logs its tool name, success/failure, latency, and
    error code without logging secrets or user-sensitive content.
  - **Verify:** Trigger a Helpdesk API fault and confirm the log records the failed
    tool call while the API returns an honest response.

## Scenario 2 quality tasks

- [x] **Implement the diagram’s “Worked?” follow-up loop**
  - **Gap:** After a documented answer, the workflow does not ask whether the
    procedure worked or branch from that answer into resolved memory versus
    escalation.
  - **Done when:** A cited troubleshooting response records an awaiting follow-up
    state; a positive answer records a useful resolution summary for the requester;
    a negative answer offers escalation, then follows the ticket draft and approval
    path. Do not file a ticket without the user choosing escalation.
  - **Verify:** Add two multi-turn cases: documented answer → “it worked” → saved
    resolution memory, and documented answer → “it did not work” → escalation draft
    → approval → one created ticket.

- [x] **Align workflow branches with the request-resolution diagram**
  - **Gap:** The core branches exist, but the code does not yet make the complete
    state-machine flow explicit: known incident, missing context, evidence, worked,
    escalation choice, draft, approval, write result, and next-step/rejection.
  - **Done when:** Session state represents each conversation decision point, and
    every diagram branch has a testable response without bypassing the approval gate.
  - **Verify:** Trace each branch in the diagram with unit or shared-format evals;
    include unknown action IDs, rejected drafts, ticket-service failures, and retry
    behavior.

- [x] **Exercise the unknown-issue escalation journey in the UI**
  - **Current behavior:** An unknown issue now offers escalation; a follow-up such
    as “Yes, please create a ticket” creates a `pending_action` and enables Approve.
  - **Done when:** The flow works in the running UI from unknown answer through
    approval and the system-of-record ticket ID.
  - **Verify:** Use the `CRM-1150` conversation, approve the draft, and confirm the
    real returned ticket appears in `/admin/tickets`.

- [x] **Run and preserve evaluation evidence**
  - **Gap:** The scorecard claims 20/20, but it should be rerun after final changes.
  - **Done when:** Supplied and owned suites pass against the current app, with the
    updated scorecard committed and summarized in the README.
  - **Verify:**
    ```bash
    python simulator/evals/run_evals.py
    python simulator/evals/run_evals.py --cases evals/cases.owned.jsonl
    ```

- [x] **Add an owned eval for two-turn unknown escalation**
  - **Gap:** The regression is covered by unit test, but not yet by the shared eval
    format used by graders.
  - **Done when:** An eval starts with an unknown issue, confirms escalation in a
    second user turn, approves the generated action, and asserts exactly one ticket
    with `category: other`, no unsupported KB references, and a real ticket ID.
  - **Verify:** Run that single case with `-v`.

## Delivery and submission tasks

- [ ] **Clean the simulator worktree**
  - **Gap:** The worktree contains changes under `simulator/`; the assignment says
    not to alter simulated-system behavior.
  - **Done when:** Simulator changes are reviewed, intentionally discarded or moved
    outside the simulator, and `git status` contains no unintended simulator files.
  - **Verify:** `git status --short`

- [ ] **Complete README portfolio artifacts**
  - **Gap:** The video URL, clone URL, team details, and visual product evidence are
    placeholders or missing.
  - **Done when:** The README has the real public repository URL, named contributors,
    a screenshot or GIF, a working three-minute video link, architecture diagram,
    real-vs-simulated table, scorecard, and honest next steps.
  - **Verify:** Clone into a fresh directory and follow the README without local
    assumptions.

- [ ] **Complete bootcamp submission metadata**
  - **Gap:** `DESIGN.md` still contains placeholder team and repository details; the
    release/check-in evidence was not available during review.
  - **Done when:** `DESIGN.md` is completed, required check-ins are posted, the
    repository is public, and the final freeze is tagged `v1.0`.
  - **Verify:** `git tag --list` includes `v1.0`; confirm the registration issue
    contains all required check-ins.

## Final verification

```bash
docker compose up --build
PYTHONPATH=. .venv/bin/python -m pytest -q
python simulator/check_kit.py
python simulator/dataset/validate_dataset.py
python simulator/evals/run_evals.py
python simulator/evals/run_evals.py --cases evals/cases.owned.jsonl
```
