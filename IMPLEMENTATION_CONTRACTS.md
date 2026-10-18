# Implementation Contracts

This document freezes the interfaces for the Message Notification Router. It defines data ownership and module boundaries; it contains no implementation logic.

## Contract conventions

- Python 3.11+ type notation is used for signatures.
- `None` means the source field is genuinely absent. Empty strings are normalized to `None` at loading boundaries.
- A module may read objects owned by another module, but may not mutate them or construct replacements for that owner’s object.
- All public functions are deterministic unless explicitly marked provider-backed.
- Provider-backed modules must return typed degraded results rather than leak provider exceptions into the batch orchestrator.
- CSV row ordering is preserved through loading and output generation.

## Shared value types

### `DatasetTables`

Purpose: immutable in-memory representation of the participant-facing CSV inputs.

Fields:

- `messages: Sequence[Mapping[str, Any]]`
- `sample_messages: Sequence[Mapping[str, Any]]`
- `users: Mapping[str, Mapping[str, Any]]`
- `groups: Mapping[str, Mapping[str, Any]]`
- `group_members: Mapping[tuple[str, str], Mapping[str, Any]]`
- `business_accounts: Mapping[str, Mapping[str, Any]]`
- `user_business_history: Mapping[tuple[str, str], Mapping[str, Any]]`
- `message_history: Mapping[str, Mapping[str, Any]]`
- `message_events: Mapping[tuple[str, str], Mapping[str, Any]]`
- `daily_notification_summary: Mapping[tuple[str, str], Mapping[str, Any]]`

Optional fields: none for required participant-facing tables.

Invariants: source keys are unique; source rows retain their original values after normalization; target message order is preserved.

Validation rules: required files and headers must be present; duplicate primary or compound keys are rejected.

Owner: `loader`.

### `MediaCatalog`

Purpose: validated lookup from media IDs to local media paths.

Fields:

- `images: Mapping[str, Path]`
- `voice_notes: Mapping[str, Path]`

Optional fields: none.

Invariants: catalog IDs are unique; paths are rooted under the supplied dataset media area; type-specific IDs are not cross-used.

Validation rules: reject duplicate IDs, unsupported path escapes, and message references absent from the relevant catalog.

Owner: `loader`.

### `PerceptionClient`

Purpose: provider boundary for image OCR and voice transcription.

Fields: provider-specific configuration is opaque to production modules.

Optional fields: provider credentials and request settings may be absent only when a deterministic degraded client is intentionally configured.

Invariants: the client returns typed modality results or raises an exception that `perception` converts to a degraded observation.

Validation rules: configuration is validated at startup; secrets are read from environment/configuration and never stored in source files.

Owner: `perception`.

### `JudgmentClient`

Purpose: provider boundary for gated content interpretation.

Fields: provider-specific configuration is opaque to production modules.

Optional fields: provider credentials and request settings may be absent only when fallback-only mode is intentionally configured.

Invariants: provider output is mapped to one of the three `ContentJudgment` labels before it leaves the module.

Validation rules: configuration is validated at startup; raw provider output cannot become a routing action.

Owner: `content_judgment`.

### `RuntimeConfig`

Purpose: immutable execution settings supplied by the entrypoint.

Fields:

- `provider_mode: Literal["real", "stub", "fallback"]`
- `perception_cache_path: Path | None`
- `judgment_cache_path: Path | None`
- `max_provider_retries: int`
- `fail_fast_on_configuration_error: bool`

Optional fields: cache paths.

Invariants: retry count is non-negative; provider mode is explicit; configuration does not contain raw secrets.

Validation rules: reject unsupported modes and negative retry counts.

Owner: `app`.

### `BatchReport`

Purpose: operational result of one complete batch run.

Fields:

- `target_count: int`
- `output_count: int`
- `degraded_count: int`
- `provider_call_count: int`
- `cache_hit_count: int`
- `output_path: Path`
- `validation_passed: bool`

Optional fields: none.

Invariants: counts are non-negative; `validation_passed` is true before a successful run is reported; output count equals target count on success.

Validation rules: reject negative counts and successful reports with incomplete output.

Owner: `orchestrator`.

### `MessageFeatures`

Purpose: normalized content and structural features for one incoming message.

Fields:

- `message_id: str`
- `message_text: str | None`
- `media_type: Literal["image", "voice"] | None`
- `media_id: str | None`
- `forwarded_count: int`
- `content_text: str | None` — original text or extracted OCR/ASR text.
- `content_language: str | None`
- `mentions_recipient: bool`
- `has_url: bool`
- `has_payment_language: bool`
- `has_otp_or_verification_language: bool`
- `has_forward_or_chain_language: bool`
- `has_urgent_language: bool`

Optional fields: all content-derived fields except `message_id`, `forwarded_count`, and `media_type`.

Invariants:

- `message_id` is non-empty.
- `forwarded_count >= 0`.
- `media_id` is present exactly when `media_type` is present.
- `content_text` is never fabricated from a missing media observation.

Validation rules: reject invalid media combinations and negative forwarding counts; normalize feature booleans to `bool`.

Owner: `features`.

### `ImageObservation`

Purpose: typed OCR result for an image message.

Fields:

- `media_id: str`
- `ocr_text: str | None`
- `confidence: float | None`
- `failed: bool`
- `failure_reason: str | None`

Optional fields: `ocr_text`, `confidence`, and `failure_reason`.

Invariants: `0 <= confidence <= 1` when present; `failure_reason` is present when `failed` is true; `ocr_text` is absent when extraction failed.

Validation rules: reject confidence outside `[0, 1]`; require a failure reason for degraded observations.

Owner: `perception`.

### `VoiceObservation`

Purpose: typed ASR result for a voice-note message.

Fields:

- `media_id: str`
- `transcript: str | None`
- `confidence: float | None`
- `failed: bool`
- `failure_reason: str | None`

Optional fields: `transcript`, `confidence`, and `failure_reason`.

Invariants and validation rules: same as `ImageObservation`, with `transcript` replacing `ocr_text`.

Owner: `perception`.

### `Observation`

Purpose: modality-neutral perception result consumed by feature extraction and content judgment.

Fields:

- `media_id: str | None`
- `media_type: Literal["image", "voice"] | None`
- `image: ImageObservation | None`
- `voice: VoiceObservation | None`

Optional fields: all fields except `media_type` for text-only messages.

Invariants:

- Text-only messages have `media_type is None` and both nested observations absent.
- Image messages have exactly one `image` observation.
- Voice messages have exactly one `voice` observation.
- Nested `media_id` matches the top-level `media_id`.

Validation rules: reject mismatched modality/nested-observation combinations.

Owner: `perception`.

### `ResolvedContext`

Purpose: read-only identity, conversation, sender, group, business, and recipient context for one message.

Fields:

- `message_id: str`
- `user_id: str`
- `conversation_type: Literal["personal", "group", "business"]`
- `created_at: datetime`
- `group_id: str | None`
- `business_id: str | None`
- `sender_user_id: str | None`
- `sender: Mapping[str, Any] | None`
- `user: Mapping[str, Any]`
- `group: Mapping[str, Any] | None`
- `group_membership: Mapping[str, Any] | None`
- `business: Mapping[str, Any] | None`
- `user_business_history: Mapping[str, Any] | None`

Optional fields: all conversation-specific IDs and records.

Invariants:

- `user_id` exists in `users.csv`.
- Group messages have a valid group and membership record for the recipient.
- Business messages have a valid business record.
- Personal messages do not require group or business records.
- A missing nullable relationship remains `None`; it is never silently replaced with a default record.

Validation rules: reject missing required identities, invalid conversation-specific foreign keys, and malformed timestamps.

Owner: `resolver`.

### `EvidenceReference`

Purpose: one validated historical message used to support a decision.

Fields:

- `message_id: str`
- `user_id: str`
- `relevance_reason: str`
- `relevance_score: float`

Optional fields: none.

Invariants: the ID exists in `message_history.csv` and belongs to the current recipient; `relevance_reason` is non-empty; score is in `[0, 1]`.

Validation rules: reject unknown IDs, wrong-user IDs, empty reasons, and out-of-range scores.

Owner: `retrieval`.

### `RiskSignals`

Purpose: safety signals, including unconditional hard overrides and advisory soft risk.

Fields:

- `hard_override: bool`
- `matched_rules: tuple[str, ...]`
- `soft_risk_score: float`
- `is_scam_like: bool`
- `is_spam_like: bool`

Optional fields: none.

Invariants:

- `0 <= soft_risk_score <= 1`.
- `hard_override` is true whenever a hard safety rule matches.
- Hard overrides do not depend on provider availability.
- `matched_rules` contains stable rule identifiers, not generated prose.

Validation rules: reject unknown rule identifiers and out-of-range scores.

Owner: `risk`.

### `PersonalizationSignals`

Purpose: recipient-specific notification preferences and engagement signals.

Fields:

- `group_muted: bool`
- `promotions_opted_out: bool`
- `quiet_hours_active: bool`
- `recent_engagement_score: float`
- `notification_load_score: float`
- `trusted_business_relationship: bool`
- `dismissal_signal: bool`

Optional fields: none; unavailable source facts are represented conservatively and recorded by the resolver validation layer.

Invariants: all booleans are explicit; scores are in `[0, 1]`; this object contains signals only, not a final action.

Validation rules: reject out-of-range scores and unknown preference states.

Owner: `personalization`.

### `ContentJudgment`

Purpose: bounded interpretation of message content when structural signals conflict.

Fields:

- `label: Literal["genuine_urgency", "generic_forward", "ambiguous"]`
- `confidence: float`
- `source: Literal["provider", "fallback"]`
- `failure_reason: str | None`

Optional fields: `failure_reason`.

Invariants: confidence is in `[0, 1]`; fallback judgments use `label="ambiguous"` and `source="fallback"`; this object never contains an action.

Validation rules: reject unsupported labels and inconsistent provider/fallback fields.

Owner: `content_judgment`.

### `DecisionInput`

Purpose: immutable aggregate consumed by the decision engine.

Fields:

- `context: ResolvedContext`
- `features: MessageFeatures`
- `risk: RiskSignals`
- `personalization: PersonalizationSignals`
- `content_judgment: ContentJudgment | None`
- `evidence: tuple[EvidenceReference, ...]`

Optional fields: `content_judgment` is present only when the conflict gate requests it.

Invariants:

- All nested objects refer to the same `message_id` and recipient.
- Content judgment is absent for non-conflict cases.
- Evidence is already validated before decision evaluation.

Validation rules: reject cross-message or cross-user object mixtures and unexpected content judgments.

Owner: `orchestrator`.

### `DecisionOutput`

Purpose: locked routing result produced by the decision engine.

Fields:

- `message_id: str`
- `action: Literal["notify", "digest", "mute"]`
- `message_type: Literal["personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"]`
- `fired_gate: str`
- `matched_signals: tuple[str, ...]`

Optional fields: none.

Invariants:

- Action and message type are valid enum values.
- Exactly one gate owns the final disposition.
- A hard safety override cannot be reversed downstream.

Validation rules: reject missing gate ownership, unsupported enum values, and contradictory gate/action combinations.

Owner: `decision`.

### `Justification`

Purpose: explanation and confidence derived from a locked decision and validated evidence.

Fields:

- `reason: str`
- `confidence: float`
- `evidence_message_ids: tuple[str, ...]`

Optional fields: none; use an empty tuple to serialize as `none`.

Invariants:

- Reason is non-empty and names the deciding mechanism.
- Confidence is in `[0, 1]`.
- Evidence IDs are a subset of the input evidence IDs.
- Justification cannot alter or contradict `DecisionOutput`.

Validation rules: reject unsupported evidence IDs, empty reasons, and confidence outside `[0, 1]`.

Owner: `justification`.

### `OutputRow`

Purpose: final CSV-compatible row.

Fields:

- `message_id: str`
- `action: Literal["notify", "digest", "mute"]`
- `message_type: Literal["personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"]`
- `reason: str`
- `confidence: float`
- `evidence_message_ids: str`

Optional fields: none.

Invariants: fields appear in the exact required order; evidence is semicolon-separated or exactly `none`; one row exists for every target message.

Validation rules: enforce exact header, row cardinality, unique message IDs, enum membership, confidence range, and evidence-ID validity.

Owner: `output`.

## Module contracts

### `loader`

Responsibility: read participant-facing CSVs and media catalog metadata into immutable source tables.

Public API:

```python
def load_dataset(dataset_dir: Path) -> tuple[DatasetTables, MediaCatalog]: ...
```

Inputs: dataset directory.

Outputs: `DatasetTables` and `MediaCatalog`, both owned by `loader`.

Exceptions: `DatasetSchemaError`, `DatasetReadError`.

Guarantees: required files, headers, and source types are validated; no prediction logic is applied.

Side effects: reads local files only.

### `resolver`

Responsibility: resolve one incoming message into `ResolvedContext`.

Public API:

```python
def resolve_context(message: Mapping[str, Any], tables: DatasetTables) -> ResolvedContext: ...
```

Inputs: one target message and loader-owned tables.

Outputs: `ResolvedContext`.

Exceptions: `ContextResolutionError` for invalid required or relationship data.

Guarantees: nullable relationships remain explicit; no content judgment or routing occurs.

Side effects: none.

### `perception`

Responsibility: inspect referenced image/audio files and return typed observations.

Public API:

```python
def perceive(message: Mapping[str, Any], media_catalog: MediaCatalog, client: PerceptionClient) -> Observation: ...
```

Inputs: message, loader-owned media catalog, provider client.

Outputs: `Observation`.

Exceptions: provider/file exceptions are absorbed into degraded observations; configuration errors may raise `PerceptionConfigurationError` before batch processing.

Guarantees: text-only rows do not invoke media perception; one media row cannot abort the batch.

Side effects: may read media and update a perception cache; must not mutate source tables.

### `features`

Responsibility: normalize message text and observations into `MessageFeatures`.

Public API:

```python
def extract_features(context: ResolvedContext, message: Mapping[str, Any], observation: Observation) -> MessageFeatures: ...
```

Inputs: resolver-owned context, message, and perception-owned observation.

Outputs: `MessageFeatures`.

Exceptions: `FeatureExtractionError` for malformed source values.

Guarantees: no final routing decision is made.

Side effects: none.

### `retrieval`

Responsibility: select and validate historical evidence for the recipient and message context.

Public API:

```python
def retrieve_evidence(context: ResolvedContext, features: MessageFeatures, tables: DatasetTables) -> tuple[EvidenceReference, ...]: ...
```

Inputs: resolver-owned context, feature object, loader-owned tables.

Outputs: validated evidence references.

Exceptions: `EvidenceRetrievalError` for malformed history tables; irrelevant candidates are excluded rather than returned.

Guarantees: every returned ID exists in history and belongs to the recipient.

Side effects: none, apart from optional read-through cache.

### `risk`

Responsibility: compute deterministic hard safety rules and an optional advisory soft score.

Public API:

```python
def assess_risk(context: ResolvedContext, features: MessageFeatures, observation: Observation | None) -> RiskSignals: ...
```

Inputs: context, features, and optional observation.

Outputs: `RiskSignals`.

Exceptions: hard-rule evaluation must not raise for provider failure; malformed input may raise `RiskInputError`.

Guarantees: hard overrides are independent of model availability and cannot be reversed by later modules.

Side effects: none; any advisory provider call is isolated behind the risk module.

### `personalization`

Responsibility: derive recipient-specific notification and relationship signals.

Public API:

```python
def assess_personalization(context: ResolvedContext, features: MessageFeatures, tables: DatasetTables) -> PersonalizationSignals: ...
```

Inputs: context, features, and loader-owned notification summaries/events.

Outputs: `PersonalizationSignals`.

Exceptions: `PersonalizationInputError` for invalid source values.

Guarantees: never emits a final action and never overrides safety signals.

Side effects: none.

### `content_judgment`

Responsibility: interpret content only for a structural conflict selected by the orchestrator/decision gate.

Public API:

```python
def judge_content(context: ResolvedContext, features: MessageFeatures, observation: Observation | None, client: JudgmentClient) -> ContentJudgment: ...
```

Inputs: context, normalized features, optional observation, provider client.

Outputs: bounded `ContentJudgment`.

Exceptions: provider failures are converted to fallback judgments; configuration errors may raise before processing.

Guarantees: never emits an action or message type; provider output cannot bypass the decision engine.

Side effects: may read/write a judgment cache.

### `decision`

Responsibility: apply the frozen gate priority and own the final routing disposition.

Public API:

```python
def decide(inputs: DecisionInput) -> DecisionOutput: ...
```

Inputs: complete `DecisionInput`.

Outputs: locked `DecisionOutput`.

Exceptions: `DecisionInputError` for invalid or incomplete aggregates; no provider exceptions are allowed.

Guarantees: exactly one gate fires; hard safety overrides have priority; no downstream module can mutate the result.

Side effects: none.

### `justification`

Responsibility: produce a decision-consistent explanation, confidence, and selected evidence IDs.

Public API:

```python
def justify(decision: DecisionOutput, evidence: tuple[EvidenceReference, ...]) -> Justification: ...
def audit_justification(decision: DecisionOutput, justification: Justification) -> None: ...
```

Inputs: decision-owned output and retrieval-owned evidence.

Outputs: `Justification`; audit returns `None` or raises.

Exceptions: `JustificationError` and `JustificationConsistencyError`.

Guarantees: cannot change the disposition; evidence is selected only from validated candidates.

Side effects: none.

### `output`

Responsibility: serialize and validate final rows.

Public API:

```python
def build_output_row(decision: DecisionOutput, justification: Justification) -> OutputRow: ...
def validate_output(rows: Sequence[OutputRow], target_message_ids: Sequence[str]) -> None: ...
def write_output(rows: Sequence[OutputRow], output_path: Path) -> None: ...
```

Inputs: decision and justification objects; target IDs; output path.

Outputs: validated `OutputRow` objects; CSV file from `write_output`.

Exceptions: `OutputValidationError`, `OutputWriteError`.

Guarantees: exact header, exact row coverage, valid enums, valid confidence, and serialized evidence format.

Side effects: writes only the requested output file.

### `orchestrator`

Responsibility: sequence modules, gate provider calls, isolate row failures, and produce the final batch.

Public API:

```python
def run_batch(dataset_dir: Path, output_path: Path, runtime: RuntimeConfig) -> BatchReport: ...
```

Inputs: dataset path, output path, runtime/provider configuration.

Outputs: `BatchReport` owned by `orchestrator`.

Exceptions: startup/configuration errors may abort before processing; row-level failures must not abort the batch.

Guarantees: one valid output row per target message, deterministic ordering, explicit degraded-row reasons, and final validation before writing.

Side effects: reads dataset/media, may use caches/providers, writes output and operational logs.

## Ownership and dependency contracts

| Object | Sole owner | Consumers |
|---|---|---|
| `DatasetTables`, `MediaCatalog` | `loader` | all lookup modules, orchestrator |
| `ResolvedContext` | `resolver` | features, retrieval, risk, personalization, content judgment |
| `Observation`, `ImageObservation`, `VoiceObservation` | `perception` | features, risk, content judgment |
| `MessageFeatures` | `features` | retrieval, risk, personalization, content judgment, orchestrator |
| `EvidenceReference` | `retrieval` | decision input, justification, output audit |
| `RiskSignals` | `risk` | decision input, decision |
| `PersonalizationSignals` | `personalization` | decision input, decision |
| `ContentJudgment` | `content_judgment` | decision input, decision |
| `DecisionInput` | `orchestrator` | decision |
| `DecisionOutput` | `decision` | justification, output |
| `Justification` | `justification` | output |
| `OutputRow` | `output` | orchestrator, CSV writer |
| `BatchReport` | `orchestrator` | evaluation/reporting |

Dependency direction:

```text
loader ──┬─> resolver ──┬─> features ──┬─> decision ──> justification ──> output
         │               ├─> retrieval ──┘             └──────────────────────┘
         │               ├─> risk ──────┘
         │               ├─> personalization ──┘
         │               └─> content_judgment ─┘
         └──────────────────────────────────────────────────────────────┘

orchestrator coordinates all modules but is not imported by them.
evaluation consumes outputs and sample labels; it is not a production dependency.
```

## Contract review

### Circular dependencies

None are permitted. The decision module consumes typed signals only and must not import perception, risk providers, or content-judgment clients. The orchestrator is the only coordinator and is not imported by production modules.

### Duplicate responsibilities

- Risk owns safety classification and hard overrides.
- Personalization owns user preference and engagement signals.
- Decision owns `action` and `message_type`.
- Justification owns `reason`, confidence, and evidence selection from already validated candidates.
- Output owns CSV serialization and final schema validation.

No module may generate a competing action or message type.

### Unnecessary abstractions removed

- No vector store, embedding service, or voting layer is contracted.
- No separate “routing policy” object is introduced; the decision engine owns the frozen gate chain.
- `ImageObservation` and `VoiceObservation` remain nested variants of `Observation` because modality-specific validation is useful while downstream consumption stays uniform.

### Hidden coupling resolved

- Cross-object identity is validated through `message_id` and recipient `user_id` invariants.
- Evidence retrieval must validate IDs before justification sees them.
- Content judgment is optional and gated; `None` means it was not requested, while `ambiguous/fallback` means it was requested but unavailable or inconclusive.
- Provider clients are passed into provider-backed functions rather than imported as global clients.

### Interview risks

- The risk soft score is advisory only; hard safety rules remain deterministic and terminal.
- Confidence is a calibrated rule output, not a provider logit.
- Degraded media/provider rows remain valid but must disclose degradation in their reason.
- The repository has no dependency manifest yet; runtime setup must be documented before implementation begins.
- The design documents cite 1,062 historical messages, but the repository contains 412. All implementation contracts use the repository’s 412-row corpus.

## Contract decision log

1. `DecisionOutput` owns the final action and message type.
2. `Justification` cannot revise a decision.
3. `ContentJudgment` never contains routing fields.
4. `EvidenceReference` is validated at retrieval time, not during prose generation.
5. Provider failure produces typed fallback results where possible; only startup/configuration failures may stop the batch.
6. The conflict gate is represented by the orchestrator/decision input contract, not by a hard-coded provider call inside the content module.
