# HackerRank Orchestrate: Production-Grade AI Support Agent

## Engineering Philosophy: Safety-First RAG
This system is built with a "Safety-First" Retrieval-Augmented Generation (RAG) approach. We fundamentally favor **Correctness over Completion**. This means the agent is programmed to immediately escalate support tickets rather than guess or hallucinate answers when it encounters ambiguous situations or lacks necessary context.

## The "Circuit Breaker" Logic
We implemented a strict circuit breaker pattern in `code/schema.py`. Using Pydantic's `@model_validator`, the system mechanically flips a ticket's status to `escalated` if the AI's own reasoning justification admits that the retrieved context "does not contain" or "does not address" the issue. This deterministic guardrail prevents hallucination leaks before they ever reach the output.

## Adversarial & Outage Handling
Robust prompt-level guardrails are embedded within `code/router.py`. These constraints explicitly instruct the LLM to detect and properly flag platform downtime (such as Resume Builder or Zoom outages) and recognize adversarial prompt injections. Instead of attempting to answer unresolvable outages, the agent categorizes them for immediate human review.

## Portability
To ensure seamless evaluation by the judges, `code/main.py` utilizes dynamic path resolution. By leveraging `os` and `pathlib`, the orchestration script will run flawlessly in any directory structure or environment without relying on hardcoded absolute paths.

## ⚙️ Setup and Execution

### Prerequisites
- Python 3.10+
- Valid API Keys for Gemini 1.5 Flash / Pro

### 1. Installation
```bash
pip install pydantic openai google-genai


The agent requires an API key to function. We support standard environment variables.
To configure the agent, set one of the following environment variables depending on your chosen model:

**macOS/Linux:**
```bash
export GEMINI_API_KEY="your-gemini-key-here"
# OR
export OPENAI_API_KEY="your-openai-key-here"
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-gemini-key-here"
# OR
$env:OPENAI_API_KEY="your-openai-key-here"
```

3. Run the Agent
Bash
python code/main.py
The resulting 29-row validated output will be generated in support_tickets/output.csv.

## 📂 Project Structure
code/main.py: Entry point and dynamic path orchestration.

code/router.py: LLM reasoning logic and escalation guardrails.

code/schema.py: Pydantic models and deterministic safety validators.

code/retriever.py: Support corpus indexing logic.