
# Computer-Use Automation System
### Design Report — interface.ai Engineering Assignment

## 1. Architecture

The system separates LLM-driven workflow discovery from deterministic execution. An LLM discovers how to complete a task through a live application interface, the successful execution is recorded as a versioned capability artifact, and subsequent executions replay that capability without requiring the model.

### System Components

- **Browser Surface (`app/surface/`)** — Playwright-based browser observation, navigation, and interaction.
- **Discovery Agent (`app/discovery/`)** — Ollama-hosted Qwen model operating through an observe → decide → act loop.
- **Artifact System (`app/artifacts/`)** — Pydantic schemas and generation of typed, reusable JSON capabilities.
- **Replay Engine (`app/replay/`)** — Deterministic execution, locator resolution, checkpoints, extraction, and error handling.
- **Safety Layer (`app/safety/`)** — Action restrictions, navigation guards, and sensitive-data protection.
- **Human Handoff (`app/handoff/`)** — Browser ownership, intervention lifecycle, FastAPI operator API, and dashboard.

### Execution Flow

```text
Natural-Language Goal
        |
        v
LLM Discovery Agent
        |
        v
Live Browser Interaction
        |
        v
Successful Discovery Evidence
        |
        v
Capability Artifact Generator
        |
        v
Versioned JSON Capability
        |
        v
Deterministic Replay Engine
        |
        v
Success / Business Outcome / Failure
        |
        +----> Human Intervention (when required)
```

**Key decision:** Use the LLM during discovery, not during production replay. This reduces inference costs and nondeterministic behavior while allowing successful workflows to be reused.

**Trade-off:** Playwright provides reliable browser interaction and accessibility-based targeting, but the implemented surface does not yet support native desktop applications or interfaces without usable DOM/accessibility information.

The system uses Docker Compose and a local mock banking application. Distributed orchestration was intentionally excluded to keep the implementation focused on the core workflow.

## 2. Artifact schema

A capability is represented as a typed, versioned JSON document validated using Pydantic.

The demonstrated capability is:

- **Capability ID:** `banking.get_savings_balance`
- **Version:** `1.0.0`
- **Input:** `member_id` (string)
- **Outputs:** `member_id`, `savings_balance`, and `currency`

The artifact contains:

1. Capability identity, version, description, and target application.
2. Typed input and output specifications.
3. Ordered execution steps.
4. Stable locator specifications.
5. Runtime parameter references.
6. Checkpoints and extraction rules.
7. Success conditions and expected business outcomes.

### Parameterization

The member identifier is stored as:

```json
{
  "value": "{{member_id}}"
}
```

At runtime, the replay engine substitutes the supplied input without changing the artifact.

### Locator Design

Supported locator strategies include:

- Attribute-based targeting
- Accessibility role and name
- Visible text
- CSS selectors

For the demonstrated workflow, named attributes and accessibility roles are preferred over positional control IDs.

**Trade-off:** Stable locators improve replay reliability but remain dependent on the application's UI contract. Locator uniqueness and checkpoint verification help detect unexpected changes.

The artifact is independent of the raw LLM transcript, making it reviewable and reusable by a calling agent.

## 3. Determinism & error handling

The replay engine loads a saved capability artifact and executes its steps without invoking the LLM.

For each action, replay:

1. Validates the current application state.
2. Detects known business outcomes.
3. Resolves the saved locator.
4. Waits for the expected control.
5. Verifies locator uniqueness.
6. Executes the permitted action.
7. Checks the expected post-action state.
8. Records execution evidence.

Extracted data is independently verified against the requested member identifier.

### Result Taxonomy

**Success**

The capability completes and returns verified outputs.

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

**Expected business outcome**

An unknown member returns a structured result rather than an exception.

```json
{
  "status": "business_outcome",
  "capability_id": "banking.get_savings_balance",
  "outcome": "member_not_found",
  "outputs": {}
}
```

**Technical failure**

Failures identify the interrupted step, error category, and whether recovery may be possible.

Examples include:

- Locator timeout
- Checkpoint failure
- Policy violation
- Session ownership failure
- Intervention timeout
- Extraction verification failure

### Recovery Strategy

The system uses bounded waits and explicit escalation rather than blindly retrying arbitrary actions.

Known business outcomes are returned directly. Recoverable UI problems may trigger human intervention. Hard failures terminate execution and preserve diagnostic evidence.

### Verified Results

| Member ID | Result | Savings Balance |
|-----------|--------|-----------------|
| 12345 | Success | $2,450.75 |
| 67890 | Success | $8,150.20 |
| 99999 | Member not found | N/A |

The latest verified regression suite completed with **52 passing tests**.

## 4. Heterogeneity & multi-tenant

The current implementation uses Playwright, but the intended architecture separates capability definitions from application-specific observation and interaction.

### Heterogeneous Surfaces

The browser surface could be extended through interchangeable adapters:

| Surface | Observation | Interaction |
|---------|-------------|-------------|
| Modern web | DOM and accessibility tree | Playwright |
| Legacy web | Frames, accessibility tree, screenshots | Frame-aware and visual controls |
| Desktop | OS accessibility APIs and screenshots | OS-level input automation |

Each adapter would expose a common interface for observation, action execution, and screenshot capture.

The replay engine would continue consuming capability artifacts, while the surface adapter would resolve how recorded actions are performed.

This extension is a design proposal; only the browser implementation exists in the prototype.

### Multi-Tenant Reuse

In production, hundreds of financial institutions may operate different configurations of the same vendor application.

Instead of recording a separate capability for every institution, artifacts could be organized around shared vendor/application families.

A proposed capability registry would store:

- Vendor and application family
- Supported application versions
- Base capability version
- Tenant-specific configuration
- Locator and route overrides
- Compatibility and approval status

A base capability would describe the logical workflow. Tenant-specific bindings would resolve differences in branding, routes, labels, and configuration.

### Drift Detection

Compatibility could be checked through:

- Checkpoint failures
- Changed UI signatures
- Locator-resolution failures
- Periodic replay validation
- Application-version metadata

A failed compatibility check would prevent unattended execution until the affected variant is reviewed.

**Trade-off:** The prototype does not implement multi-tenant infrastructure or desktop adapters. These are documented extension points rather than partially implemented production features.

## 5. Escalation & handoff

The system supports human intervention when automation cannot safely proceed or when a controlled demonstration explicitly requires manual assistance.

### Session Ownership Model

The browser session has six states:

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
   +----> COMPLETED

Any nonterminal state
   |
   +----> FAILED
```

A `BrowserSession` tracks the active Playwright page, current owner, execution step, and intervention reason.

An `InterventionManager` creates and manages requests for operator assistance.

### Human Intervention Workflow

1. Automation encounters a condition requiring intervention.
2. The session transitions to `paused`.
3. An intervention request records the interrupted capability, step, and reason.
4. An authorized operator acquires control.
5. The operator performs approved actions on the same Playwright page.
6. The operator releases control.
7. Automation resumes and verifies the current application state.

The same browser session is preserved throughout the handoff.

### Post-Intervention Reconciliation

After the operator releases control, replay checks whether the interrupted step's expected checkpoint is already satisfied.

If Search was completed by the operator, automation avoids submitting Search a second time.

If the required state is not reached, the system returns an explicit failure instead of assuming success.

### Verified Handoff Evidence

A successful operator-assisted replay was recorded under:

`3f58aed51c5f4518814772ba2c02b926`

Recorded events include:

```text
intervention_requested
automation_resumed
step_completed_by_operator
replay_completed
```

The final replay status was `success`.

The implementation provides a functional operator dashboard with screenshot preview, session status, intervention controls, and approved manual actions.

A full remote-desktop/co-browsing interface was intentionally excluded.

## 6. Safety

The prototype applies explicit restrictions to browser navigation and action execution.

### Application Allowlist

Automation is restricted to approved routes within the fictional mock banking application.

Navigation to external domains and unapproved routes is blocked.

### Action Restrictions

The safety layer distinguishes permitted read-oriented operations from risky or irreversible actions.

Allowed actions include approved member lookup interactions.

Actions involving transfers, deletion, or other unapproved operations are blocked.

### Session Ownership

Only the active session owner may perform browser actions.

Automation cannot operate while a human owns the session, and an unauthorized operator cannot release another operator's control.

### Sensitive Data Protection

The system includes:

- Operator-token authentication for API requests
- Environment-based secret configuration
- Evidence redaction
- Structured failure reporting
- Restricted browser actions
- Unique locator validation

The mock banking application uses fictional data and does not connect to real financial systems.

**Limitation:** This is not a production banking security implementation. Production deployment would require stronger authentication, authorization, audit logging, persistent secret management, and regulated-data handling controls.

## 7. Cuts

The project prioritizes a complete end-to-end vertical slice over a broad automation platform.

### Deliberately Excluded

**Native desktop automation:** Only Playwright browser automation is implemented. Desktop accessibility and visual-control adapters remain proposed extensions.

**Multi-tenant infrastructure:** Shared vendor capabilities, tenant overrides, and compatibility registries are designed but not implemented.

**Distributed execution:** Sessions are managed in memory within a single operator service rather than through persistent workers and queues.

**Full remote co-browsing:** The dashboard uses screenshots and approved action forms instead of unrestricted remote desktop interaction.

**General-purpose recovery:** Recovery is bounded and workflow-specific. The prototype does not attempt arbitrary autonomous recovery.

**Production-grade security:** The implementation demonstrates allowlists, ownership enforcement, and redaction, but not enterprise identity management or comprehensive operator audit trails.

### Next Improvements

With additional time, the highest-priority improvements would be:

1. Generalized browser and desktop surface adapters.
2. Shared capability definitions with tenant-specific overrides.
3. Persistent session and intervention state.
4. Stronger operator-action auditing.
5. Broader runtime error classification and safe recovery policies.

### Conclusion

The implementation demonstrates the complete core workflow:

**Natural-language goal → LLM-driven UI discovery → reusable capability artifact → deterministic replay → verified result or human intervention.**

The system successfully performs parameterized savings-balance retrieval, distinguishes expected business outcomes from technical failures, enforces safety restrictions, and supports operator-assisted replay on the same browser session.

The central design principle is that the LLM discovers a workflow once, while deterministic replay provides a repeatable execution path for subsequent invocations.
