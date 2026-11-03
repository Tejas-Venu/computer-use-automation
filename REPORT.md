
# Technical Report: Computer-Use Automation System

## 1. Executive Summary

This project implements a computer-use automation prototype that transforms LLM-guided browser discovery into reusable, deterministic automation capabilities.

The system demonstrates the workflow using a fictional banking administration portal.

Its primary capability, `banking.get_savings_balance`, retrieves a member's savings balance from the application's user interface.

The implementation combines LLM-assisted discovery, versioned capability artifacts, deterministic Playwright replay, safety controls, evidence recording, and human-in-the-loop intervention.

The latest regression suite completed with 52 passing tests.

## 2. Problem Statement

Traditional browser automation frequently depends on manually written selectors and fixed execution scripts.

LLM-based browser agents offer flexibility but can introduce nondeterministic behavior, additional inference costs, and difficulties with reproducibility.

This project separates workflow discovery from execution.

The LLM discovers a successful workflow once. The system records its actions and UI evidence, generates a versioned capability, and subsequently executes that capability without additional LLM calls.

Human intervention provides a controlled recovery mechanism when automation requires operator assistance.

## 3. System Architecture

The implementation contains six primary subsystems.

### 3.1 Browser Surface

The browser surface uses Playwright to navigate the application, inspect controls, interact with elements, and capture screenshots.

Implementation:

`app/surface/browser.py`

### 3.2 LLM Discovery

The discovery agent observes the browser and requests structured action decisions from an Ollama-hosted Qwen model.

Supported discovery actions include filling inputs, clicking controls, extracting information, and terminating execution.

The discovery runner records action history and stable locator information.

Implementation:

- `app/discovery/agent.py`
- `app/discovery/runner.py`
- `app/discovery/schemas.py`
- `app/discovery/completion.py`

### 3.3 Capability Artifact System

Successful discovery evidence is converted into a versioned JSON capability.

The artifact describes inputs, outputs, actions, locators, checkpoints, extraction rules, and expected outcomes.

Implementation:

- `app/artifacts/schema.py`
- `app/artifacts/generator.py`

### 3.4 Deterministic Replay

The replay engine loads the saved capability and executes browser actions without invoking the LLM.

The engine uses parameter substitution, stable locators, UI checkpoints, structured extraction, and business-outcome verification.

Implementation:

- `app/replay/engine.py`
- `app/replay/locators.py`
- `app/replay/checkpoints.py`
- `app/replay/outcomes.py`
- `app/replay/waits.py`

### 3.5 Safety and Evidence

The safety subsystem restricts navigation and browser actions to the approved mock application.

The evidence subsystem records execution events and supports failure diagnostics.

Implementation:

- `app/safety/policy.py`
- `app/safety/guard.py`
- `app/safety/navigation.py`
- `app/replay/evidence.py`

### 3.6 Human Intervention

The handoff subsystem manages browser ownership and intervention requests.

The same Playwright page is preserved while control transfers from automation to a human operator.

Implementation:

- `app/handoff/session.py`
- `app/handoff/intervention.py`
- `app/handoff/controller.py`
- `app/handoff/service.py`
- `app/handoff/api.py`

The frontend is implemented using HTML, CSS, and JavaScript.

## 4. Capability Demonstration

Capability ID:

`banking.get_savings_balance`

Version:

`1.0.0`

Input:

```json
{
  "member_id": "12345"
}
```

The workflow consists of four actions:

1. Enter the member ID.
2. Submit the search.
3. Open member details.
4. Extract and verify the savings balance.

Expected output:

```json
{
  "member_id": "12345",
  "savings_balance": "2450.75",
  "currency": "USD"
}
```

The member ID is parameterized, allowing the same capability to execute for different members.

## 5. Discovery and Artifact Generation

The initial discovery successfully identified the required browser interactions and retrieved the savings balance.

The discovery runner recorded the sequence and associated UI locators.

The artifact generator validated the discovery sequence and converted the recorded controls into stable locator specifications.

This avoids relying on positional control IDs during replay.

The artifact also includes extraction and verification rules for the savings balance.

## 6. Deterministic Replay

Replay executes the saved artifact without invoking Ollama.

For each step, the engine:

1. Checks the current application state.
2. Detects known business outcomes.
3. Resolves the saved locator.
4. Verifies locator uniqueness and availability.
5. Executes the approved action.
6. Validates the configured checkpoint.
7. Records execution evidence.

At extraction, the engine verifies that the returned balance belongs to the requested member.

### Verified replay results

| Member ID | Outcome | Balance |
|---|---|---|
| 12345 | Success | USD 2450.75 |
| 67890 | Success | USD 8150.20 |
| 99999 | Member not found | N/A |

These cases demonstrate successful parameterized execution and structured handling of a missing member.

## 7. Human-in-the-Loop Design

Human intervention is implemented using a shared browser session.

The session state machine includes:

- Running
- Paused
- Human control
- Resuming
- Completed
- Failed

When intervention is requested, automation pauses and releases browser ownership.

An authorized operator can acquire control, perform an approved action, and release control.

Automation then revalidates the browser state before continuing.

The demo workflow pauses before submitting the member search.

The operator can complete Search using the dashboard's manual browser controls.

After resumption, the replay engine checks whether the Search checkpoint has already been satisfied.

This prevents an unnecessary duplicate Search click when the operator has completed that step.

## 8. Human Intervention Evidence

A successful operator-assisted replay was recorded with run ID:

`3f58aed51c5f4518814772ba2c02b926`

The recorded evidence includes:

```text
intervention_requested
automation_resumed
step_completed_by_operator
replay_completed
```

Final status:

`success`

These records demonstrate successful intervention, resumption, checkpoint recognition, and workflow completion.

The replay evidence establishes the operator-completed checkpoint path. A separate manual-action API audit event was not independently verified.

## 9. Safety Model

The prototype uses a restrictive safety policy.

It limits automation to approved mock banking routes and actions.

The system rejects unauthorized navigation and potentially dangerous operations.

Additional safeguards include:

- Browser ownership enforcement
- Approved action validation
- Unique locator checks
- Explicit intervention transitions
- Failure-state handling
- Evidence redaction
- Structured error identifiers

The design is intended for a controlled demonstration environment.

## 10. Testing and Evaluation

The latest full regression suite produced:

```text
52 passed, 1 warning
```

The tests cover:

- Capability schema validation
- Structured extraction
- Browser locator resolution
- Checkpoint verification
- Business-outcome detection
- Failure evidence
- Safety and navigation policies
- Browser session ownership
- Intervention lifecycle
- Live browser handoff
- Managed replay integration
- Operator API authentication

The remaining warning relates to a Starlette/httpx test-client deprecation and did not cause a test failure.

### Evaluation summary

The tests and replay results support the following conclusions:

- Parameterized deterministic replay works for the tested members.
- The system handles missing-member outcomes.
- Safety restrictions reject tested unauthorized actions.
- Browser handoff preserves the same Playwright page in integration testing.
- Managed replay can resume after a simulated intervention.
- An operator-assisted checkpoint path completed successfully.
- The operator dashboard can initiate and monitor replay.

These results establish functionality for the tested mock application, not general reliability across arbitrary websites.

## 11. Engineering Challenges

### Stable Locators

Positional control IDs were unsuitable for reusable replay.

The implementation records locator specifications based on UI attributes and accessibility roles.

### LLM Output Reliability

During discovery, the Ollama model occasionally returned empty responses when generation ended at the output-token limit.

The discovery implementation was adjusted to improve structured response reliability.

### Business Outcomes

An unknown member initially produced a missing-locator failure.

The replay engine was updated to distinguish an expected `member_not_found` outcome from a technical failure.

### Human Handoff

The implementation required coordination between browser actions and ownership transitions.

Shared locking, intervention state management, and post-intervention checkpoint verification were introduced to support safe handoff.

### Session Failure States

A failed intervention could leave the dashboard displaying a nonterminal session state.

Explicit failure handling was introduced to keep the session lifecycle consistent.

## 12. Limitations

The current prototype has several limitations.

First, the application under test is a fictional banking portal with a narrow workflow.

Second, the operator dashboard provides a screenshot preview and approved manual-action forms rather than a full remote desktop.

Third, browser sessions and intervention state are held in memory, so process restarts terminate active sessions.

Fourth, the implementation is intended for a single operator service instance.

Fifth, recovery and checkpoint reconciliation are designed for the demonstrated workflow and are not a general solution for irreversible transactions.

Finally, production deployment would require stronger operator authentication, authorization, audit logging, secret management, and operational monitoring.

## 13. Future Improvements

Potential improvements include:

- Persistent session and intervention metadata
- Richer operator audit trails
- More general capability discovery and generation
- Multiple supported application workflows
- Improved locator resilience
- More detailed replay telemetry
- Stronger operator identity management
- Production-grade recovery policies
- Expanded end-to-end testing

## 14. Conclusion

This project demonstrates a practical approach to combining LLM-driven workflow discovery with deterministic browser automation.

The separation between discovery and replay enables reuse of successful workflows without repeated LLM inference.

Versioned capability artifacts, safety checks, evidence recording, and human intervention provide structure around execution.

The implementation successfully demonstrated parameterized savings-balance retrieval, expected business-outcome handling, and operator-assisted replay in the fictional banking environment.
