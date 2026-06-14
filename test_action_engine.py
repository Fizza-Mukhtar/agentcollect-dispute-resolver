"""
test_action_engine.py

Runs the full pipeline: classify_transcript() -> recommend_action()
for every sample in sample_transcripts.json, and prints the resulting
action plan for each.

Usage:
    python3 test_action_engine.py
"""

import json
import os
from classifier import classify_transcript
from action_engine import recommend_action


def run_pipeline():
    with open("sample_transcripts.json") as f:
        data = json.load(f)

    mode = "LIVE (Claude API)" if os.environ.get("ANTHROPIC_API_KEY") else "MOCK (offline heuristic)"
    print(f"Running full pipeline in mode: {mode}")
    print("=" * 70)

    for sample in data["transcripts"]:
        classification = classify_transcript(sample["messages"])
        plan = recommend_action(classification, invoice_ref=sample["invoice_ref"])

        print(f"\n--- {sample['id']} (invoice {sample['invoice_ref']}, {sample['amount']}, {sample['days_overdue']}d overdue) ---")
        print(f"Classification: {plan['category']} (confidence: {plan['confidence']}, tier: {plan['confidence_tier']})")
        print(f"Pause sequence: {plan['pause_sequence']}")
        print(f"Notify: {plan['notify']}")
        print(f"Action: {plan['action']}")
        if plan["followup_message"]:
            print(f"Follow-up message:\n  \"{plan['followup_message']}\"")


if __name__ == "__main__":
    run_pipeline()