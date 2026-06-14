"""
test_classifier.py

Runs classify_transcript() against every sample in sample_transcripts.json
and reports expected vs actual category + confidence.

Usage:
    python3 test_classifier.py

Works in both modes:
    - If ANTHROPIC_API_KEY is set: uses the real LLM classifier
    - If not set: uses the offline mock heuristic (clearly labeled in output)
"""

import json
import os
from classifier import classify_transcript


def run_tests():
    with open("sample_transcripts.json") as f:
        data = json.load(f)

    mode = "LIVE (Claude API)" if os.environ.get("ANTHROPIC_API_KEY") else "MOCK (offline heuristic)"
    print(f"Running classifier in mode: {mode}")
    print("=" * 70)

    results = []
    correct = 0

    for sample in data["transcripts"]:
        result = classify_transcript(sample["messages"])

        is_correct = result.get("category") == sample["expected_category"]
        correct += int(is_correct)

        results.append({
            "id": sample["id"],
            "invoice_ref": sample["invoice_ref"],
            "expected": sample["expected_category"],
            "actual": result.get("category"),
            "confidence": result.get("confidence"),
            "match": "✅" if is_correct else "❌",
            "reasoning": result.get("reasoning"),
        })

    for r in results:
        print(f"\n[{r['match']}] {r['id']} (invoice {r['invoice_ref']})")
        print(f"    Expected:   {r['expected']}")
        print(f"    Got:        {r['actual']}  (confidence: {r['confidence']})")
        print(f"    Reasoning:  {r['reasoning']}")

    print("\n" + "=" * 70)
    print(f"Score: {correct}/{len(results)} correct")

    return results


if __name__ == "__main__":
    run_tests()