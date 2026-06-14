# AgentCollect — Dispute Resolution Module

A dispute classification and routing engine designed to slot into AgentCollect's
AI-powered recovery pipeline.

## What this does

When a debtor raises a dispute during an AI agent call/email (e.g., "I already
paid this", "this isn't the right amount"), this module:

1. Classifies the dispute into one of 6 categories
2. Extracts relevant entities (payment dates, reference numbers, disputed amounts)
3. Returns a confidence score and reasoning trace

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
```

## Usage

```bash
python3 test_classifier.py
```

Without an API key set, this runs in offline mock mode (keyword heuristic)
so the pipeline structure can still be verified end-to-end.

## Files

- `dispute_categories.md` — taxonomy definition (6 categories, evidence
  requirements, confidence thresholds)
- `sample_transcripts.json` — 5 realistic transcripts (RetellAI-style format),
  one per dispute category
- `classifier.py` — core classification engine
- `test_classifier.py` — test runner against sample data

## Why this matters for AgentCollect

The "happy path" (debtor agrees to pay) is the easy 80%. Disputes are where
automation either builds trust or burns it — misclassifying "already paid" as
"fraud" (or vice versa) has real consequences for a Fortune 500 brand's
relationship with their customers. This module is a first pass at making that
routing decision reliable, auditable, and easy to extend.