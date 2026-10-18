# orchestrate_integration_kit/

Plugs into ANY cloned HackerRank Orchestrate repository. Redesigned around **augmentation, not generation** — this assumes a real repo already exists and needs to be understood, extended, and audited, not scaffolded from zero.

## Only inputs you provide, per competition
- The cloned repository
- Problem statement
- Dataset / sample data
- API documentation
- Submission rules

## Pipeline (run in this order)

```
1. python analyzers/repo_analyzer.py --repo <cloned_repo> \
       --out REPOSITORY_ANALYSIS.md --json-out repo_analysis.json
   ↓ (real static analysis: entrypoints, schemas, tests, missing imports — verified
      to independently rediscover a real known bug in testing, see kit changelog)

2. Feed the Problem Analyzer frontend prompt (see ir.py's docstring / PROMPT_LIBRARY.md #1-2
   context) + your 4 raw inputs to a coding agent → save output as problem_ir.json
   ↓ (the one step requiring judgment — same role as a compiler's semantic-analysis pass)

3. python analyzers/gap_analyzer.py --repo-analysis repo_analysis.json \
       --problem-ir problem_ir.json --out IMPLEMENTATION_PLAN.md --tasks-out tasks.json
   ↓ (diffs what exists against what's needed; honest LIKELY_PRESENT / LIKELY_MISSING /
      NEEDS_HUMAN_REVIEW classification, never silently guesses)

4. Work tasks.json using PROMPT_LIBRARY.md, following COMPETITION_WORKFLOW.md's hour-by-hour
   schedule. Run REFLECTION_LOOP.md after each task.

5. python analyzers/output_audit.py --csv output.csv --problem-ir problem_ir.json \
       --out OUTPUT_AUDIT.md
   ↓ (schema/enum/duplicate/justification-diversity checks — verified against a real,
      previously-audited output.csv with zero false positives)

6. Run LOCAL_JUDGE.md.

7. python interview_compiler.py --repo-analysis repo_analysis.json --problem-ir problem_ir.json \
       --tasks tasks.json --out INTERVIEW_PREP.md
   ↓ then run PROMPT_LIBRARY.md #17 for a live adversarial mock interview.

8. Submit, using COMPETITION_WORKFLOW.md's checklist.
```

## Files
```
orchestrate_integration_kit/
├── README.md                          (this file)
├── ir.py                              (ProblemIR schema — same contract as the earlier compiler)
├── analyzers/
│   ├── repo_analyzer.py               (repo -> REPOSITORY_ANALYSIS.md, tested & verified)
│   ├── gap_analyzer.py                (repo_analysis + problem_ir -> IMPLEMENTATION_PLAN.md + tasks.json, tested & verified)
│   └── output_audit.py                (output.csv -> OUTPUT_AUDIT.md, tested & verified)
├── interview_compiler.py              (final repo state -> INTERVIEW_PREP.md, tested & verified)
├── prompts/
│   └── PROMPT_LIBRARY.md              (20 prompts, each with when/inputs/outputs/mistakes/follow-up)
├── LOCAL_JUDGE.md                     (self-scoring framework, mapped to the reverse-engineered theory)
├── COMPETITION_WORKFLOW.md            (hour-by-hour, augmentation-first)
└── TRANSCRIPT_AND_REFLECTION_AND_META.md
```

## What's real vs. what's a template
The three analyzer scripts and `interview_compiler.py` are **executable Python, tested against real data** — `repo_analyzer.py` independently rediscovered a genuine bug from a past submission (two missing perception-client imports) using zero domain knowledge, purely from AST parsing. `output_audit.py` correctly returned zero false positives against a real, clean 44-row output file. `gap_analyzer.py` correctly fuzzy-matched real classes (`EvidenceValidator`, `UserHistoryRow`) to IR requirements with honest, non-overclaimed confidence scores.

The workflow/prompt/judge docs are templates by necessity — they encode *process*, which can't be unit-tested the way code can. Their content is traceable to the reverse-engineered judging theory, not generic hackathon advice.

## Honest limitation
The gap analyzer's matching is name/structure-based (fuzzy string + token overlap), not semantic. It will miss a correctly-implemented gate that happens to be named unrelatedly, and it will falsely flag a plausibly-named stub that doesn't actually work. This is why every match carries a confidence score and a `NEEDS_HUMAN_REVIEW` tier instead of a binary yes/no — the tool is honest about the boundary of what static analysis can and can't tell you, which is the same discipline it's trying to help you build into your own submissions.
