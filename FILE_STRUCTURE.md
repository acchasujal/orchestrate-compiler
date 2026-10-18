# File Structure

This layout maps the frozen architecture onto the current repository. It keeps deterministic modules independently testable and leaves provider-backed code behind narrow interfaces.

```text
.
├── AGENTS.md
├── README.md
├── problem_statement.md
├── RESEARCH_REPORT.md
├── ARCHITECTURE_DESIGN.md
├── IMPLEMENTATION_PLAYBOOK.md
├── IMPLEMENTATION_CONTRACTS.md
├── FILE_STRUCTURE.md
├── dataset/
│   ├── messages.csv
│   ├── sample_messages.csv
│   ├── output.csv
│   ├── users.csv
│   ├── groups.csv
│   ├── group_members.csv
│   ├── business_accounts.csv
│   ├── user_business_history.csv
│   ├── message_history.csv
│   ├── message_events.csv
│   ├── images.csv
│   ├── voice_notes.csv
│   ├── daily_notification_summary.csv
│   └── media/
├── code/
│   ├── main.py
│   ├── app/
│   │   └── orchestrator.py
│   ├── loader/
│   │   ├── tables.py
│   │   └── schemas.py
│   ├── models/
│   │   └── contracts.py
│   ├── resolver/
│   │   └── context_resolver.py
│   ├── features/
│   │   └── message_features.py
│   ├── retrieval/
│   │   └── evidence_retriever.py
│   ├── risk/
│   │   └── risk_scorer.py
│   ├── personalization/
│   │   └── personalization_scorer.py
│   ├── perception/
│   │   ├── perception.py
│   │   ├── clients.py
│   │   └── cache.py
│   ├── content_judgment/
│   │   ├── content_judgment.py
│   │   └── clients.py
│   ├── decision/
│   │   └── decision_engine.py
│   ├── justification/
│   │   └── justification.py
│   ├── output/
│   │   └── output_writer.py
│   ├── utils/
│   │   ├── errors.py
│   │   └── time.py
│   └── evaluation/
│       ├── main.py
│       └── metrics.py
└── tests/
    ├── unit/
    ├── integration/
    ├── regression/
    └── fixtures/
```

## Directory responsibilities

### `code/app/`

Owns batch orchestration and runtime configuration. It sequences modules but contains no domain scoring rules.

### `code/loader/`

Owns CSV/media-catalog loading and source-schema validation. It is the only module that constructs `DatasetTables` and `MediaCatalog`.

### `code/models/`

Owns shared typed contracts only. It contains no lookup, scoring, provider, or routing logic.

### `code/resolver/`

Owns identity and relationship joins that produce `ResolvedContext`.

### `code/features/`

Owns normalization of text, media observations, and structural content signals into `MessageFeatures`.

### `code/retrieval/`

Owns bounded historical candidate selection and `EvidenceReference` validation.

### `code/risk/`

Owns deterministic safety hard-triggers and the advisory risk score. It never owns the final action.

### `code/personalization/`

Owns recipient-specific preferences, engagement, relationship, and notification-load signals.

### `code/perception/`

Owns image/audio file inspection, typed observations, provider adapters, and perception caching.

### `code/content_judgment/`

Owns the gated bounded content interpretation and its provider adapter. It returns `ContentJudgment`, never a routing decision.

### `code/decision/`

Owns the frozen gate chain and is the sole owner of `DecisionOutput`.

### `code/justification/`

Owns decision-consistent reasons, confidence bands, evidence selection from validated candidates, and the contradiction audit.

### `code/output/`

Owns `OutputRow`, final schema validation, and CSV serialization.

### `code/utils/`

Owns narrow cross-cutting utilities that do not contain domain policy. It must not become a dumping ground for routing logic.

### `code/evaluation/`

Owns local comparison against `sample_messages.csv`, output audits, and evaluation reports. Production code must not import it.

### `tests/`

Contains contract, module, integration, regression, and failure-injection tests. Fixtures are test-owned and must not be used as prediction labels in production.

## Import rules

- `models` imports no project modules.
- `loader` imports only standard-library/data parsing dependencies and `models` if needed for source-table types.
- `resolver`, `retrieval`, `risk`, and `personalization` may depend on `loader` and `models`.
- `perception` and `content_judgment` may depend on `models` and provider adapter interfaces, but not on `decision` or `output`.
- `features` may depend on `models` and `perception` types.
- `decision` may depend only on `models`.
- `justification` may depend on `models`.
- `output` may depend on `models`.
- `app/orchestrator.py` may depend on all production modules.
- `evaluation` and `tests` may consume production modules, but production modules may not import them.

## Placement decisions

- `main.py` remains the terminal entrypoint required by the repository contract.
- `evaluation/main.py` remains the local evaluation entrypoint rather than becoming part of production execution.
- Provider clients are kept inside their owning provider-backed modules; no global provider singleton is required.
- Shared dataclasses/protocols live in `models/contracts.py` so module interfaces do not create circular imports.
- The design does not introduce a separate `policy/` directory; the decision engine is the single policy owner.
