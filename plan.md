# NetCoop AI implementation plan

## Product scope
NetCoop AI is a transparent, synthetic-telemetry network fault diagnosis workbench for an AI hackathon demo. It keeps the original rule-based multi-agent architecture: a Performance Agent analyzes latency, loss, jitter, and utilization; an Infrastructure Agent analyzes CPU, interface errors, queue drops, and Wi-Fi signal; the Orchestrator validates, correlates, and emits a structured JSON report. The website must run without external credentials, support the five supplied scenarios and custom JSON upload, show the agents' structured messages, and make the report inspectable/downloadable.

## Implementation approach
- Preserve `netcoop.py` as the domain engine, refactoring it into readable, typed, testable functions with an explicit message contract and report schema.
- Replace the fragile Streamlit-only entry point with a small Flask server (`app.py`) serving a responsive single-page dashboard and JSON endpoints (`/api/scenarios`, `/api/diagnose`, `/healthz`). This makes local preview and container publication deterministic while keeping the diagnosis engine framework-independent.
- Keep all supplied telemetry under `data/` and add API + unit tests covering every scenario, invalid payloads, structured agent messages, and report serialization.
- Serve `public/manus-routes.json` for the managed Webdev route manifest and add `Dockerfile`, `.dockerignore`, and deployment documentation.

## Design direction
Three candidate styles: Signal-room noir (0.06) — dark operations-console energy with luminous telemetry; Editorial systems lab (0.08) — bright, typographic, research-report calm; Circuit glass (0.04) — layered glass panels with electric gradients and dense data readouts.

Chosen style: **Signal-room noir**.

- **Design Movement:** Mission-control dashboards and Swiss information design, tuned for an AI systems demo rather than a generic admin panel.
- **Core Principles:** Explain the reasoning; make system state legible; use contrast to prioritize action; keep the operator in control.
- **Color Philosophy:** Ink/navy surfaces establish trust and focus. An ownable electric-lime signal color marks healthy/active system state, while amber and coral are reserved for warnings and faults.
- **Layout Paradigm:** A left rail establishes context and run controls; the main canvas moves from an evidence-led hero to a wide diagnosis result and a two-column agent handoff trace. Avoid a centered marketing grid.
- **Signature Elements:** A thin “signal rail” progress line, compact mono labels, and glowing status dots that echo packet flow.
- **Interaction Philosophy:** One decisive run action, immediate run-state feedback, expandable evidence, and no hidden work. JSON is always one click away.
- **Animation:** Subtle 150–250ms panel transitions and a live pulse on the active signal rail; avoid distracting motion during diagnosis.
- **Typography System:** Inter for UI/headings, IBM Plex Mono for IDs, metrics, timestamps, and JSON. Strong 12px uppercase labels with generous tracking.
- **Brand Essence:** “A transparent second opinion for network incidents” — forensic, calm, explainable.
- **Brand Voice:** Direct and evidence-led. Example lines: “Trace the signal. Isolate the fault.” and “Two agents. One defensible report.”
- **Wordmark & Logo:** A compact `N` mark built from two converging traces, paired with the NetCoop wordmark.
- **Signature Brand Color:** Electric lime `#C7F36B`.

## Project structure
- `app.py`: Flask server, API routes, static asset serving.
- `netcoop.py`: validation, two agent analyzers, structured message contract, orchestration/report generation.
- `data/`: supplied sample telemetry scenarios.
- `public/`: frontend HTML, CSS, JavaScript, and route manifest.
- `tests/`: engine and API regression coverage.
- `Dockerfile`: reproducible production container on port 3000.
