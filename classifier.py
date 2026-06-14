"""
classifier.py

Core dispute classification engine for AgentCollect's recovery pipeline.

Takes a call/email transcript (list of {role, content} turns) and returns a
structured classification: dispute category, confidence score, extracted
entities, and a brief reasoning trace.

This module is intentionally LLM-driven rather than keyword-based:
real debtor phrasing varies too much for rules to hold up, and AgentCollect's
entire stack is already AI-native (RetellAI voice agents, AI-powered QA, etc.)
"""

import json
import os
from anthropic import Anthropic

# --------------------------------------------------------------------------
# Categories (kept in sync with dispute_categories.md)
# --------------------------------------------------------------------------

DISPUTE_CATEGORIES = [
    "Already Paid",
    "Wrong Amount",
    "Service Not Received",
    "Need Manager Approval",
    "Fraud Claim",
    "Other / Unclear",
]

SYSTEM_PROMPT = """You are a dispute classification engine for AgentCollect, \
a B2B debt collection platform. You analyze call and email transcripts between \
an AI recovery agent and a debtor, and classify any dispute the debtor raises.

Categories you can assign:
- "Already Paid": debtor claims the invoice has already been settled
- "Wrong Amount": debtor disputes the invoiced amount (pricing/overcharge issue)
- "Service Not Received": debtor claims the goods/service were never delivered
- "Need Manager Approval": debtor needs internal sign-off before paying (NOT a dispute, but affects routing)
- "Fraud Claim": debtor claims the invoice itself is illegitimate
- "Other / Unclear": none of the above, or intent is ambiguous

For each transcript, return ONLY a JSON object (no markdown fences, no preamble) \
with this exact structure:

{
  "category": "<one of the categories above, exact string match>",
  "confidence": <integer 0-100>,
  "extracted_entities": {
    "claimed_payment_date": "<string or null>",
    "claimed_payment_method": "<string or null>",
    "reference_number": "<string or null>",
    "disputed_amount": "<string or null>",
    "other_notes": "<string or null>"
  },
  "reasoning": "<one sentence explaining why this category and confidence>"
}

Be conservative with confidence: only use 80+ when the debtor's intent is \
explicit and unambiguous. If multiple issues are raised, classify by the \
PRIMARY/first dispute raised. If no dispute is present at all (debtor is \
cooperative, asks for a payment plan, etc.), this should not happen in this \
dataset, but if it does, use "Other / Unclear" with low confidence and note \
it in reasoning."""


def _mock_classify(messages: list[dict]) -> dict:
    """
    Offline fallback classifier used when no ANTHROPIC_API_KEY is configured.

    This is NOT the production classification logic -- it's a simple keyword
    heuristic so the pipeline can be exercised end-to-end (demos, CI, offline
    dev) without API access. The real classify_transcript() below is the
    actual engine and is what runs when an API key is present.
    """
    text = " ".join(turn["content"] for turn in messages if turn["role"] == "debtor").lower()

    rules = [
        ("Already Paid", ["already paid", "sent payment", "paid that", "paid this"]),
        ("Wrong Amount", ["wrong amount", "wrong price", "doesn't look right", "different number", "rate"]),
        ("Service Not Received", ["never got", "never delivered", "never received", "no idea what this is"]),
        ("Fraud Claim", ["scam", "don't recognize", "never ordered", "fraud"]),
        ("Need Manager Approval", ["check with my manager", "run this by", "not authorized", "ask finance"]),
    ]

    for category, keywords in rules:
        if any(kw in text for kw in keywords):
            return {
                "category": category,
                "confidence": 65,
                "extracted_entities": {
                    "claimed_payment_date": None,
                    "claimed_payment_method": None,
                    "reference_number": None,
                    "disputed_amount": None,
                    "other_notes": "Classified via offline mock heuristic (no API key set)",
                },
                "reasoning": f"Mock mode: matched keyword heuristic for '{category}'",
                "_mode": "mock",
            }

    return {
        "category": "Other / Unclear",
        "confidence": 30,
        "extracted_entities": {
            "claimed_payment_date": None,
            "claimed_payment_method": None,
            "reference_number": None,
            "disputed_amount": None,
            "other_notes": "Classified via offline mock heuristic (no API key set)",
        },
        "reasoning": "Mock mode: no keyword rule matched",
        "_mode": "mock",
    }


def classify_transcript(messages: list[dict], client: Anthropic | None = None) -> dict:
    """
    Classify a single transcript.

    Args:
        messages: list of {"role": "agent"|"debtor", "content": str, ...}
                  (extra keys like timestamps are ignored)
        client: optional pre-constructed Anthropic client (for reuse across calls)

    Returns:
        dict matching the JSON schema described in SYSTEM_PROMPT.

    If no ANTHROPIC_API_KEY is set in the environment and no client is passed,
    falls back to an offline mock heuristic (see _mock_classify) so the rest
    of the pipeline can still be exercised. Production runs will always have
    an API key configured and will use the real LLM classifier.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return _mock_classify(messages)
        client = Anthropic()

    # Flatten transcript into a readable conversation block
    transcript_text = "\n".join(
        f"{turn['role'].upper()}: {turn['content']}" for turn in messages
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Classify this transcript:\n\n{transcript_text}",
            }
        ],
    )

    raw_text = response.content[0].text.strip()

    # Defensive: strip markdown fences if the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        result = {
            "category": "Other / Unclear",
            "confidence": 0,
            "extracted_entities": {},
            "reasoning": f"PARSE_ERROR: model output was not valid JSON ({e})",
            "_raw_output": raw_text,
        }

    # Validate category is one of the known set; fall back safely if not
    if result.get("category") not in DISPUTE_CATEGORIES:
        result["_validation_warning"] = (
            f"Unexpected category '{result.get('category')}', "
            f"expected one of {DISPUTE_CATEGORIES}"
        )

    return result


if __name__ == "__main__":
    # Quick smoke test using the first sample transcript
    with open("sample_transcripts.json") as f:
        data = json.load(f)

    sample = data["transcripts"][0]
    print(f"Testing transcript {sample['id']} (expected: {sample['expected_category']})")
    print("-" * 60)

    result = classify_transcript(sample["messages"])
    print(json.dumps(result, indent=2))