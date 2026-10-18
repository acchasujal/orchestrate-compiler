# PROMPT_DECISION_TREE.md
*Find your situation, use the numbered prompt. No situation on this list → default to #1 (Repository Review) before doing anything else; acting on an unfamiliar situation without reading first is the single most common way to lose ownership signal.*

```
Just cloned the repo, don't know what's in it
  → 1. Repository Review

Have a new requirement, unsure if existing architecture fits
  → 2. Architecture Review

Have a raw problem statement, no success criterion yet
  → 3. Problem Analysis

Need to add a genuinely new capability (not extend an existing one)
  → 4. Feature Design → then → 5. Implementation

Have an agreed plan/design already, ready to write code
  → 5. Implementation

Code works but structure is bad / hard to extend
  → 6. Refactoring   (only if some test coverage already exists — otherwise → 9 first)

Output is wrong
  → 7. Debugging
      ↳ cause still unclear after attribution
        → 8. Hypothesis-Driven Investigation

About to implement or just implemented a decision gate
  → 9. Testing

Dataset has (or might have) adversarial/edge-case patterns
  → 10. Hidden-Test / Adversarial Robustness

Need a real accuracy number, not a guess
  → 11. Evaluation

Worried about wall-clock time / API cost
  → 12. Performance   (only after measuring — see template)

Haven't tested what happens if a provider call fails or rate-limits mid-run
  → 13. Operational Resilience

Just finished a pipeline run, have an output.csv
  → 14. Output/CSV Validation

Down to the last 60–90 minutes
  → 15. Submission Audit

Preparing for the live AI judge interview
  → 16. Interview Preparation
```

## Compressed hour-by-hour mapping
```
Hour 0        → 1, then 3
Hour 0.5–2    → 2, 4 (as needed per feature)
Hour 2–8      → 5, repeated per task; 9 immediately after each decision gate
Hour 8–12     → 13 (once perception integration begins)
Hour 12–15    → 7, 8 (as failures surface); 10 (first pass)
Hour 15–17    → 14, after every full run
Hour 17–20    → 11
Hour 20–21    → 10 (second pass), 16 (rough pass)
Hour 21–23    → 15
Hour 23–24    → 16 (final pass), submit
```

## The one meta-rule
If you're about to send a prompt that starts with "just" or "quickly" — stop. That's usually the tell that a planning/attribution step (2, 3, 4, 7, or 8) is being skipped in favor of jumping straight to 5. The 30 seconds it costs to name which template applies is cheaper than the transcript signal you lose by skipping it.
