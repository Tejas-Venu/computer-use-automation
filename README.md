
# Computer-Use Automation System

A human-in-the-loop computer-use automation system that discovers workflows using an LLM, converts successful discoveries into versioned capability artifacts, and replays them deterministically without requiring further LLM inference.

The project demonstrates browser automation against a fictional banking administration portal.

## Features

- LLM-driven workflow discovery using Ollama and Qwen
- Versioned, parameterized capability artifacts
- Deterministic browser replay using Playwright
- Stable element locators and execution checkpoints
- Structured extraction and business-outcome verification
- Safety policies and navigation restrictions
- Human intervention with browser-session preservation
- FastAPI operator API and web dashboard
- Execution evidence and failure screenshots
- Automated tests covering replay, safety, and handoff

## Architecture

```text
Operator Dashboard
       |
       v
FastAPI Operator Service
       |
       v
BrowserSession + InterventionManager
       |
       v
SharedBrowserController
       |
       v
Playwright Browser
       |
       v
Mock Banking Application
```

The system has two primary execution modes.

### Discovery

The discovery agent uses an LLM to inspect the browser, choose actions, and record successful interactions.

A successful discovery provides the evidence used to generate a reusable capability artifact.

### Deterministic Replay

The replay engine loads a saved capability artifact and executes its steps without calling the LLM.

It uses stable locators, checkpoints, extraction rules, and output verification.

## Project Structure

```text
app/
  artifacts/      Capability schema and generation
  discovery/      LLM discovery and completion verification
  handoff/        Browser ownership, intervention, API, dashboard
  replay/         Deterministic execution and evidence
  safety/         Action and navigation restrictions
  surface/        Playwright browser abstraction

mock_bank/        Fictional banking application
artifacts/        Versioned capability JSON
evidence/         Discovery and replay evidence
tests/            Automated tests
```

## Requirements

- Python 3.12-compatible environment
- Docker Desktop and Docker Compose
- Playwright
- FastAPI
- Ollama with the configured Qwen model for discovery

Ollama is optional when running saved capabilities.

## Setup

### 1. Configure environment variables

Create a `.env` file in the project root.

```env
OPERATOR_TOKEN=replace-with-a-random-secret
```

Generate a token locally:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit `.env` to version control.

### 2. Start the services

```bash
docker compose up -d --build mock-bank operator
```

### 3. Open the operator dashboard

Visit:

http://localhost:8080

Enter the operator token configured in `.env`.

## Running Deterministic Replay

Retrieve member 12345:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 12345
```

Retrieve member 67890:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 67890
```

Test an unknown member:

```bash
docker compose run --rm automation \
  python -m app.replay.engine 99999
```

Successful output includes:

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

An unknown member returns a structured `member_not_found` business outcome.

## LLM Discovery

Discovery uses the Ollama server and configured Qwen model.

Start Ollama and ensure the model is available.

Then run:

```bash
docker compose run --rm automation \
  python -m app.discovery.runner
```

The discovery process records browser actions, stable locator information, and extracted outputs.

## Capability Generation

Generate a reusable capability artifact from recorded discovery:

```bash
docker compose run --rm automation \
  python -m app.artifacts.generator
```

The generated artifact is stored at:

```text
artifacts/banking.get_savings_balance.v1.json
```

The artifact includes:

- Capability ID and version
- Input and output specifications
- Ordered actions
- Stable locators
- Checkpoints
- Extraction rules
- Success conditions
- Expected business outcomes

## Human-in-the-Loop Demonstration

1. Open the operator dashboard.
2. Enter the operator token and member ID.
3. Enable **Require human intervention (demo)**.
4. Start automation.
5. Wait for the `submit_search` intervention.
6. Click **Take Control**.
7. Execute the approved Search action using the manual controls.
8. Click **Resume Automation**.
9. Verify that replay continues and returns the savings balance.

The automation and operator use the same Playwright page.

The replay engine checks the post-intervention state before continuing.

## Safety

The demonstration is restricted to the fictional mock banking application.

Safety controls include:

- Approved application routes
- Restricted browser actions
- Navigation guards
- Unique locator requirements
- Session ownership checks
- Structured failure reporting
- Sensitive-data redaction in recorded evidence

This project is a controlled prototype, not a production banking integration.

## Testing

Run the complete automated test suite:

```bash
docker compose run --rm automation \
  python -m pytest tests/ -v
```

Latest verified result:

```text
52 passed, 1 warning
```

The warning is a Starlette/httpx test-client deprecation warning.

## Evidence

Replay evidence is stored under:

```text
evidence/replay/
```

A verified successful operator-assisted run recorded:

- `intervention_requested`
- `automation_resumed`
- `step_completed_by_operator`
- `replay_completed`

Run ID:

```text
3f58aed51c5f4518814772ba2c02b926
```

The operator-completed checkpoint is recorded, although a separate manual-action API audit record has not been independently verified.

## Limitations

- The demonstration targets a fictional banking application.
- The operator dashboard uses screenshots rather than full remote desktop streaming.
- Browser session state is maintained in memory.
- The prototype is designed for a single persistent operator service.
- Manual intervention requires an available operator.
- Recovery behavior is limited to supported workflow steps.
- Additional authorization, auditing, and resilience would be required for production deployment.

## Stopping Services

```bash
docker compose down
```

For discovery environments, Ollama can be stopped separately.

## Technical Report

See [REPORT.md](REPORT.md) for implementation details, evaluation results, design decisions, and limitations.
