
# Computer-Use Automation System

A human-in-the-loop computer-use automation system that uses an LLM to discover workflows through a live user interface, records successful executions as reusable capability artifacts, and replays those capabilities deterministically without an LLM in the execution loop.

Built for the **interface.ai Software Engineer Take-Home Assignment**.

The implementation demonstrates an end-to-end workflow against a fictional banking administration portal with no integration API used by the automation.

## Features

- **LLM-driven discovery:** Ollama-hosted Qwen vision-language model performs an observe → decide → act loop.
- **Reusable capabilities:** Successful discoveries are converted into typed, versioned, parameterized JSON artifacts.
- **Deterministic replay:** Playwright executes saved capabilities without additional LLM decisions.
- **Stable locators:** Attribute-based and accessibility-role targeting, with checkpoint verification.
- **Structured outcomes:** Distinguishes successful execution, expected business outcomes, and technical failures.
- **Safety guardrails:** Restricts navigation and actions using explicit policies.
- **Human-in-the-loop intervention:** Transfers control of the same live browser session between automation and an operator.
- **Operator dashboard:** FastAPI backend with a browser screenshot preview, session status, intervention controls, and execution activity.
- **Execution evidence:** Structured discovery and replay logs, with screenshots for debugging.
- **Automated tests:** Tests covering artifact validation, replay, safety, browser ownership, and human handoff.

## Architecture

The system separates discovery from execution.

```text
                      Natural-Language Goal
                                |
                                v
                      LLM Discovery Agent
                         (Ollama / Qwen)
                                |
                                v
                       Browser Surface
                          (Playwright)
                                |
                                v
                    Successful Discovery
                         + Evidence
                                |
                                v
                       Artifact Generator
                                |
                                v
                     Versioned JSON Capability
                                |
                                v
                     Deterministic Replay Engine
                                |
                                v
                    Verified Execution Result
                                |
                  +-------------+-------------+
                  |             |             |
                  v             v             v
               Success      Business       Technical
                            Outcome        Failure
                                              |
                                              v
                                      Human Intervention
                                      (when recoverable)
```

The main components are:

| Component | Responsibility |
|-----------|----------------|
| `app/surface/` | Browser observation and interaction |
| `app/discovery/` | LLM-guided workflow discovery |
| `app/artifacts/` | Capability schema and generation |
| `app/replay/` | Deterministic execution and verification |
| `app/safety/` | Action and navigation restrictions |
| `app/handoff/` | Human intervention and browser ownership |
| `mock_bank/` | Fictional banking administration application |

### Design Principle

**The LLM discovers. The artifact records. Deterministic replay executes.**

The model is used to discover the workflow, not to make decisions during subsequent replay executions.

## Project Structure

```text
computer-use-automation/
├── app/
│   ├── artifacts/
│   │   ├── generator.py
│   │   └── schema.py
│   ├── discovery/
│   │   ├── agent.py
│   │   ├── completion.py
│   │   ├── runner.py
│   │   └── schemas.py
│   ├── handoff/
│   │   ├── api.py
│   │   ├── controller.py
│   │   ├── intervention.py
│   │   ├── service.py
│   │   ├── session.py
│   │   └── static/
│   │       ├── app.js
│   │       ├── index.html
│   │       └── styles.css
│   ├── replay/
│   │   ├── checkpoints.py
│   │   ├── engine.py
│   │   ├── evidence.py
│   │   ├── locators.py
│   │   ├── outcomes.py
│   │   └── waits.py
│   ├── safety/
│   │   ├── guard.py
│   │   ├── navigation.py
│   │   └── policy.py
│   ├── surface/
│   │   └── browser.py
│   └── main.py
├── mock_bank/
│   └── main.py
├── artifacts/
│   └── banking.get_savings_balance.v1.json
├── evidence/
│   ├── discovery/
│   └── replay/
├── tests/
├── Dockerfile
├── compose.yaml
├── .env.example
├── README.md
└── REPORT.md
```

## Requirements

- Docker Desktop with Docker Compose
- Python 3.12-compatible environment
- Ollama for LLM-driven discovery
- Qwen model: `qwen3-vl:4b`

Python, Playwright, FastAPI, and other application dependencies are installed through the project's Docker image.

**Ollama is required for discovery but not for deterministic replay.**

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Tejas-Venu/computer-use-automation.git
cd computer-use-automation
```

### 2. Configure environment variables

Create a `.env` file:

```bash
cp .env.example .env
```

Replace the placeholder operator token with a randomly generated secret.

Generate a token:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Your `.env` should contain:

```env
OPERATOR_TOKEN=your-generated-random-token
```

Do not commit `.env` or real credentials to Git.

The operator token authenticates requests to the local operator API.

### 3. Start the application

```bash
docker compose up -d --build mock-bank operator
```

This starts:

| Service | Address | Purpose |
|---------|---------|---------|
| Mock Bank | http://localhost:8000 | Fictional banking administration UI |
| Operator Dashboard | http://localhost:8080 | Automation monitoring and human intervention |

Both services are intended for local development.

### 4. Verify the services

```bash
docker compose ps
```

Open the operator dashboard:

http://localhost:8080

Enter the operator token from `.env`.

## End-to-End Demo

This section demonstrates the complete required workflow:

**Natural-language goal → LLM discovery → saved artifact → deterministic replay → verified outputs.**

### Step 1 — Start Ollama

Install Ollama from:

https://ollama.com

Download the configured model:

```bash
ollama pull qwen3-vl:4b
```

Ensure the Ollama server is running.

On systems where Ollama is not already running:

```bash
ollama serve
```

The Docker automation service connects to Ollama using:

```text
http://host.docker.internal:11434
```

The configured model is:

```text
qwen3-vl:4b
```

### Step 2 — Run LLM-driven discovery

The discovery agent accepts a natural-language goal, a member identifier, a target URL, and a maximum step count.

Run:

```bash
docker compose run --rm automation \
  python -m app.discovery.runner \
  --member-id 12345 \
  --goal "Find member 12345, open their details, and read their savings balance." \
  --target-url http://mock-bank:8000 \
  --max-steps 10
```

The discovery agent uses the LLM to choose actions against the live browser interface.

The successful demonstrated sequence is:

| Step | Action | Description |
|------|--------|-------------|
| 1 | Fill | Enter member ID `12345` |
| 2 | Click | Submit the Search form |
| 3 | Click | Open member details |
| 4 | Extract | Read and verify the savings balance |

The model's selected actions, reasoning, and locator specifications are recorded.

A successful discovery returns:

```json
{
  "status": "success",
  "outputs": {
    "member_id": "12345",
    "savings_balance": "2450.75",
    "currency": "USD"
  }
}
```

Discovery evidence is saved to:

```text
evidence/discovery/run.json
evidence/discovery/final.png
```

The current implementation is specialized for the mock banking savings-balance workflow. Although the goal and target URL are configurable inputs, the safety policy restricts execution to the approved mock banking application, and the completion verifier expects a savings-balance result.

### Step 3 — Generate the reusable capability

After successful discovery, run:

```bash
docker compose run --rm automation \
  python -m app.artifacts.generator
```

This generates:

```text
artifacts/banking.get_savings_balance.v1.json
```

The artifact is typed, versioned, and parameterized.

It includes:

- Capability ID and version
- Description and target application
- Typed input parameters
- Typed output specifications
- Ordered actions
- Stable locator definitions
- Runtime parameter references
- Checkpoints
- Extraction rules
- Success conditions
- Expected business outcomes

The recorded member ID is replaced with the runtime parameter:

```text
{{member_id}}
```

This allows the same capability to execute for different members without repeating discovery.

### Step 4 — Run deterministic replay

Replay the saved capability:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 12345
```

Expected result:

```json
{
  "status": "success",
  "capability_id": "banking.get_savings_balance",
  "outputs": {
    "member_id": "12345",
    "savings_balance": "2450.75",
    "currency": "USD"
  }
}
```

**No LLM inference is performed during deterministic replay.**

The replay engine loads the artifact, resolves its locators, executes approved actions, verifies checkpoints, and extracts the requested outputs.

### Step 5 — Demonstrate parameterization

Run the same saved artifact with a different member:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 67890
```

Expected result:

```json
{
  "status": "success",
  "capability_id": "banking.get_savings_balance",
  "outputs": {
    "member_id": "67890",
    "savings_balance": "8150.20",
    "currency": "USD"
  }
}
```

No new discovery run or capability generation is required.

### Step 6 — Demonstrate an expected business outcome

Run:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 99999
```

Expected result:

```json
{
  "status": "business_outcome",
  "capability_id": "banking.get_savings_balance",
  "outcome": "member_not_found",
  "outputs": {}
}
```

A missing member is treated as a legitimate business outcome rather than a technical failure.

## Capability Artifact

The reusable capability is stored at:

```text
artifacts/banking.get_savings_balance.v1.json
```

### Input Contract

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `member_id` | String | Yes | Member identifier |

### Output Contract

| Field | Type | Description |
|-------|------|-------------|
| `member_id` | String | Verified member identifier |
| `savings_balance` | String | Savings balance |
| `currency` | String | Currency code |

### Recorded Actions

```text
enter_member_id
       |
       v
submit_search
       |
       v
open_details
       |
       v
extract_balance
```

The capability uses stable locator specifications rather than replaying positional control IDs recorded during discovery.

Checkpoints verify that the expected UI state was reached before proceeding.

## Deterministic Replay and Error Handling

The replay engine implements a structured execution process.

For each step:

1. Validate the current application state.
2. Check for known business outcomes.
3. Resolve the saved locator.
4. Wait for the required control.
5. Verify locator uniqueness.
6. Execute the approved action.
7. Verify the configured checkpoint.
8. Record execution evidence.

The system distinguishes three result categories.

### Success

The requested capability completes and returns verified outputs.

### Expected Business Outcome

A known application outcome, such as `member_not_found`, is returned without treating it as an automation crash.

### Technical Failure

A technical failure identifies the interrupted step and error category.

Examples include:

- Locator timeout
- Checkpoint failure
- Policy violation
- Extraction verification failure
- Session ownership failure
- Intervention timeout

The system uses bounded waiting and explicit escalation rather than unrestricted autonomous retries.

## Human-in-the-Loop Demonstration

The system supports operator intervention using the same live Playwright browser session.

### Start the operator dashboard

```bash
docker compose up -d --build mock-bank operator
```

Open:

http://localhost:8080

Enter the operator token configured in `.env`.

### Demonstration Procedure

1. Enter Member ID `12345`.
2. Enable **Require human intervention (demo)**.
3. Click **Start Automation**.
4. Wait until the session pauses at `submit_search`.
5. Click **Take Control**.
6. Verify that the session state changes to `human_control`.
7. Configure the manual browser controls as follows:

| Setting | Value |
|---------|-------|
| Action | `Click` |
| Locator Strategy | `Role` |
| Role | `button` |
| Accessible Name | `Search` |

8. Click **Execute Manual Action**.
9. Verify that the browser navigates to `/search`.
10. Click **Resume Automation**.
11. Wait for the remaining replay steps to complete.
12. Verify that the savings balance is returned successfully.

### Session State Machine

```text
RUNNING
   |
   v
PAUSED
   |
   v
HUMAN_CONTROL
   |
   v
RESUMING
   |
   v
RUNNING
   |
   v
COMPLETED

Any nonterminal state
   |
   +----> FAILED
```

The `BrowserSession` tracks the current owner and prevents automation from acting while the human operator owns the session.

After the operator releases control, replay verifies the current UI state.

If the operator already completed Search, replay recognizes the satisfied checkpoint and avoids repeating the action.

The dashboard provides a screenshot-based browser preview, session status, intervention controls, and approved manual actions.

It does not provide unrestricted remote-desktop control.

## Safety and Policy Guardrails

The system uses explicit restrictions to limit automation behavior.

### Navigation Restrictions

Automation is restricted to the approved mock banking application and permitted routes.

External navigation and unapproved routes are blocked.

### Action Restrictions

The safety layer permits approved read-oriented operations and blocks risky or irreversible actions.

Examples of blocked actions include transfers and deletion.

### Session Ownership

Only the active session owner may execute browser actions.

Automation cannot act while a human operator controls the browser.

Unauthorized operators cannot release another operator's session.

### Sensitive Data Handling

The implementation includes:

- Environment-based operator token configuration
- API token authentication
- Sensitive-string redaction in evidence
- Structured error reporting
- Restricted browser navigation
- Unique locator validation

The mock banking application contains fictional member data.

**This project is a controlled prototype, not a production banking integration.**

Production deployment would require stronger authentication, authorization, audit logging, secret management, and regulated-data handling.

## Evidence and Observability

Execution evidence is stored under:

```text
evidence/
├── discovery/
│   ├── run.json
│   └── final.png
└── replay/
    └── <run-id>/
        └── run.json
```

Failure runs may also include screenshots.

### LLM Discovery Evidence

The discovery record includes:

- Natural-language goal
- Ordered model-selected actions
- Action reasoning
- Recorded locator specifications
- Application URLs
- Verified outputs

### Deterministic Replay Evidence

Replay records execution events, including:

- Replay started
- Step started
- Step completed
- Business outcome detected
- Intervention requested
- Automation resumed
- Replay completed or failed

### Verified Operator-Assisted Replay

A successful operator-assisted replay was recorded under:

```text
evidence/replay/3f58aed51c5f4518814772ba2c02b926/run.json
```

The recorded events include:

```text
intervention_requested
automation_resumed
step_completed_by_operator
replay_completed
```

The final replay status was `success`.

The evidence confirms operator-completed checkpoint recognition. A separate, comprehensive manual-action API audit trail is not independently established by this record.

## Testing

Run the complete automated test suite:

```bash
docker compose run --rm automation \
  python -m pytest tests/ -v
```

Latest verified regression result:

```text
52 passed, 1 warning
```

The warning relates to a Starlette/httpx test-client deprecation.

### Test Coverage

The test suite covers:

- Capability schema validation
- Extraction and completion verification
- Locator resolution
- UI checkpoints
- Business outcomes
- Replay failure evidence
- Sensitive-data redaction
- Safety policy enforcement
- Navigation restrictions
- Browser session ownership
- Intervention lifecycle
- Live browser handoff
- Managed replay
- Operator API authentication

The automated tests validate the demonstrated mock banking workflow and its supported failure scenarios.

They do not establish general reliability across arbitrary websites or native desktop applications.

## Design for Heterogeneity and Multi-Tenant Reuse

The current implementation uses a Playwright browser surface.

The architecture separates the capability artifact from the application-specific observation and interaction mechanism.

### Heterogeneous Surfaces

Future surface adapters could support:

| Surface | Observation | Interaction |
|---------|-------------|-------------|
| Modern web | DOM and accessibility tree | Playwright |
| Legacy web | Frames, accessibility information, screenshots | Frame-aware and visual controls |
| Native desktop | OS accessibility APIs and screenshots | OS-level input automation |

Only the Playwright browser implementation is included in this prototype.

### Multi-Tenant Reuse

In a production environment, multiple institutions may operate different configurations of the same vendor application.

A future capability registry could support:

- Shared vendor-level capability definitions
- Application-version metadata
- Tenant-specific route and locator overrides
- Compatibility checks
- Version-drift detection
- Approval states for unattended execution

These extensions are described in the technical report but are not implemented.

## Limitations and Trade-offs

The prototype intentionally focuses on a complete, tested vertical slice rather than a broad automation platform.

Current limitations include:

- One fictional banking application.
- A savings-balance lookup capability rather than arbitrary workflow support.
- Playwright-based browser automation only.
- No native desktop automation.
- No multi-tenant capability registry.
- In-memory browser session and intervention state.
- A single persistent operator service.
- Screenshot-based browser preview rather than full remote co-browsing.
- Workflow-specific recovery and checkpoint reconciliation.
- No production-grade operator identity management or comprehensive audit infrastructure.

These cuts prioritize deterministic execution, structured artifacts, safety, and human handoff.

## Stopping Services

Stop the project containers:

```bash
docker compose down
```

Stop the Qwen model if it is running:

```bash
ollama stop qwen3-vl:4b
```

Ollama can be stopped separately when discovery is no longer needed.

## Technical Report

See [REPORT.md](REPORT.md) for the design decisions, artifact schema, deterministic replay strategy, heterogeneity and multi-tenant design, human escalation, safety model, and deliberate scope cuts.

## Repository

https://github.com/Tejas-Venu/computer-use-automation
