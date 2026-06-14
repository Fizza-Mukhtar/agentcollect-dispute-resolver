# Dispute Categories

This file defines the dispute taxonomy used by the classifier. Each category includes
typical phrasing, required evidence, and the recommended next action — designed to slot
into AgentCollect's recovery pipeline (white-label voice + email agents).

---

## 1. Already Paid
- **Description:** Debtor claims the invoice has already been settled.
- **Example phrases:** "I already paid this", "We sent payment last week", "That's been taken care of"
- **Required evidence:** Payment date, payment method, transaction/reference number
- **Recommended action:** Pause active outreach sequence → request proof of payment → escalate to finance verification queue

## 2. Wrong Amount
- **Description:** Debtor disputes the invoiced amount (overcharge, pricing mismatch, etc.)
- **Example phrases:** "This isn't the right amount", "We were charged the wrong price", "Our PO says a different number"
- **Required evidence:** Original PO/contract, agreed pricing terms
- **Recommended action:** Hold collection on disputed amount → flag for client finance team review → resume on remaining undisputed balance if applicable

## 3. Service Not Received
- **Description:** Debtor claims the goods/service tied to the invoice were never delivered.
- **Example phrases:** "We never got this", "This was never delivered", "Nobody on our side ordered this"
- **Required evidence:** Delivery confirmation, signed receipt, fulfillment record
- **Recommended action:** Pause outreach → escalate to account manager (human) → do not continue automated sequence until resolved

## 4. Need Manager Approval
- **Description:** Debtor needs internal sign-off before committing to payment.
- **Example phrases:** "I need to check with my manager", "Let me run this by finance", "I'm not authorized to approve this"
- **Required evidence:** None
- **Recommended action:** Schedule follow-up (3–5 business days) → continue gentle reminder cadence → no escalation needed yet

## 5. Fraud Claim
- **Description:** Debtor claims the invoice itself is illegitimate or fraudulent.
- **Example phrases:** "This looks like a scam", "We never ordered this", "I don't recognize this company"
- **Required evidence:** Original signed contract/agreement
- **Recommended action:** Immediate human escalation → pause ALL automation on this account → flag for compliance review

## 6. Other / Unclear
- **Description:** Doesn't cleanly fit the above categories, or intent is ambiguous.
- **Example phrases:** (varies — context-dependent)
- **Required evidence:** N/A
- **Recommended action:** Flag for human review → do not auto-resolve

---

## Confidence Threshold

- **≥ 80%** → Auto-route to recommended action
- **50–79%** → Suggest action, require human confirmation
- **< 50%** → Auto-classify as "Other / Unclear", route to human review