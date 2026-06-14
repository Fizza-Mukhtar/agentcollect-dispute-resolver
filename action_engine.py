"""
action_engine.py

Next-action recommendation engine for AgentCollect's recovery pipeline.

Takes the output of classify_transcript() (category + confidence + entities)
and decides:
  1. What action to take (auto-resolve, request evidence, escalate, etc.)
  2. Whether the active recovery sequence should be paused
  3. Who needs to be notified (none, finance team, account manager, compliance)
  4. If evidence is needed, generates a short follow-up message requesting it

This is the routing/decision layer -- it does NOT call the LLM again for
classification. It uses the confidence thresholds defined in
dispute_categories.md plus category-specific routing rules.
"""

import json
import os
from anthropic import Anthropic

# --------------------------------------------------------------------------
# Confidence thresholds (kept in sync with dispute_categories.md)
# --------------------------------------------------------------------------

CONFIDENCE_AUTO_ROUTE = 80   # >= this: auto-route to recommended action
CONFIDENCE_SUGGEST = 50      # >= this: suggest action, require human confirm
                              # < this: "Other / Unclear", route to human


# --------------------------------------------------------------------------
# Category -> routing rules
#
# Each rule defines:
#   - pause_sequence: should automated outreach stop immediately?
#   - notify: who gets flagged (None, "finance", "account_manager", "compliance")
#   - requires_evidence: does resolution need debtor-provided proof?
#   - evidence_description: what to ask for (used in follow-up message)
#   - base_action: human-readable action label
# --------------------------------------------------------------------------

ROUTING_RULES = {
    "Already Paid": {
        "pause_sequence": True,
        "notify": "finance",
        "requires_evidence": True,
        "evidence_description": "proof of payment (date, method, and transaction/reference number)",
        "base_action": "Request payment confirmation, then verify with finance",
    },
    "Wrong Amount": {
        "pause_sequence": True,
        "notify": "finance",
        "requires_evidence": True,
        "evidence_description": "the original PO or pricing agreement",
        "base_action": "Hold disputed amount, request documentation, flag for finance review",
    },
    "Service Not Received": {
        "pause_sequence": True,
        "notify": "account_manager",
        "requires_evidence": False,
        "evidence_description": None,
        "base_action": "Escalate to account manager -- do not continue automated sequence",
    },
    "Need Manager Approval": {
        "pause_sequence": False,
        "notify": None,
        "requires_evidence": False,
        "evidence_description": None,
        "base_action": "Schedule follow-up in 3-5 business days, continue gentle reminder cadence",
    },
    "Fraud Claim": {
        "pause_sequence": True,
        "notify": "compliance",
        "requires_evidence": False,
        "evidence_description": None,
        "base_action": "Immediate escalation -- pause ALL automation on this account",
    },
    "Other / Unclear": {
        "pause_sequence": True,
        "notify": "account_manager",
        "requires_evidence": False,
        "evidence_description": None,
        "base_action": "Flag for human review -- classification was not confident enough to auto-route",
    },
}


# --------------------------------------------------------------------------
# Follow-up message generation (LLM-based, with offline fallback)
# --------------------------------------------------------------------------

FOLLOWUP_SYSTEM_PROMPT = """You write short, polite follow-up messages for \
AgentCollect, a B2B debt collection platform. These messages are sent (via \
email or as a voice agent script line) to a debtor, under the CLIENT'S brand \
-- never mention AgentCollect by name.

The message should:
- Be 2-3 sentences max
- Acknowledge what the debtor said
- Politely request the specific evidence needed
- Sound professional, warm, and non-confrontational
- NOT mention "AI", "agent", "automation", or "AgentCollect"

Return ONLY the message text, no preamble, no quotes, no markdown."""


def _mock_followup_message(category: str, evidence_description: str, invoice_ref: str) -> str:
    """Offline fallback for follow-up message generation."""
    return (
        f"Thanks for letting us know about invoice {invoice_ref}. "
        f"To help our team resolve this quickly, could you share {evidence_description} "
        f"at your earliest convenience? We appreciate your help in getting this sorted out."
    )


def generate_followup_message(
    category: str,
    evidence_description: str,
    invoice_ref: str,
    client: Anthropic | None = None,
) -> str:
    """
    Generate a short follow-up message requesting evidence from the debtor.
    Falls back to a templated message if no API key is configured.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return _mock_followup_message(category, evidence_description, invoice_ref)
        client = Anthropic()

    user_prompt = (
        f"The debtor raised a '{category}' dispute regarding invoice {invoice_ref}. "
        f"We need them to provide: {evidence_description}. "
        f"Write the follow-up message."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=FOLLOWUP_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()


# --------------------------------------------------------------------------
# Main entry point: classification result -> action plan
# --------------------------------------------------------------------------

def recommend_action(classification: dict, invoice_ref: str = "this invoice") -> dict:
    """
    Takes the output of classify_transcript() and returns an action plan.

    Args:
        classification: dict from classify_transcript() with keys
                         "category", "confidence", "extracted_entities", "reasoning"
        invoice_ref: invoice reference string, used in generated messages

    Returns:
        dict with:
            - "category": str (passthrough)
            - "confidence": int (passthrough)
            - "confidence_tier": "auto" | "suggested" | "needs_review"
            - "pause_sequence": bool
            - "notify": str | None
            - "action": str (human-readable description)
            - "followup_message": str | None (only if evidence is required)
    """
    category = classification.get("category", "Other / Unclear")
    confidence = classification.get("confidence", 0)

    # Determine confidence tier
    if confidence >= CONFIDENCE_AUTO_ROUTE:
        tier = "auto"
    elif confidence >= CONFIDENCE_SUGGEST:
        tier = "suggested"
    else:
        tier = "needs_review"
        # Low confidence overrides category -> treat as Other/Unclear for routing
        category = "Other / Unclear"

    rule = ROUTING_RULES.get(category, ROUTING_RULES["Other / Unclear"])

    result = {
        "category": category,
        "confidence": confidence,
        "confidence_tier": tier,
        "pause_sequence": rule["pause_sequence"],
        "notify": rule["notify"],
        "action": rule["base_action"],
        "followup_message": None,
    }

    # If this tier requires human confirmation, note it in the action text
    if tier == "suggested":
        result["action"] = f"[SUGGESTED -- needs human confirmation] {rule['base_action']}"
    elif tier == "needs_review":
        result["action"] = f"[NEEDS REVIEW -- low confidence] {rule['base_action']}"

    # Generate follow-up message if evidence is required (only for auto/suggested tiers)
    if rule["requires_evidence"] and tier in ("auto", "suggested"):
        result["followup_message"] = generate_followup_message(
            category=category,
            evidence_description=rule["evidence_description"],
            invoice_ref=invoice_ref,
        )

    return result


if __name__ == "__main__":
    # Quick smoke test with a hand-built classification result
    sample_classification = {
        "category": "Already Paid",
        "confidence": 72,
        "extracted_entities": {
            "claimed_payment_date": "last Tuesday",
            "claimed_payment_method": None,
            "reference_number": None,
            "disputed_amount": None,
            "other_notes": None,
        },
        "reasoning": "Debtor explicitly claims payment was already sent.",
    }

    plan = recommend_action(sample_classification, invoice_ref="#4821")
    print(json.dumps(plan, indent=2))