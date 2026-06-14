# Dispute Resolution Skill

**MCP Server:** `agentcollect-dispute-resolver`
**Purpose:** Classify disputes raised by debtors during recovery calls/emails,
and determine the correct next action -- without needing a human to read every
transcript.

## When to use this

Use this skill whenever a debtor's response during a recovery sequence
contains pushback, a claim, or anything other than agreement to pay. Examples
of trigger phrases: "I already paid", "this isn't right", "we never got this",
"I need to check with someone", "this looks like a scam".

If the debtor is cooperative and simply discussing payment terms/timing with
no objection, this skill is NOT needed -- let the standard recovery flow
continue.

## Tools available

### `resolve_dispute(transcript, invoice_ref)`
**Use this for almost everything.** Runs the full pipeline in one call:
classifies the dispute AND returns the action plan (pause/notify/action +
follow-up message if needed).

Input:
```json
{
  "transcript": [
    {"role": "agent", "content": "..."},
    {"role": "debtor", "content": "..."}
  ],
  "invoice_ref": "#4821"
}
```

Output:
```json
{
  "classification": {
    "category": "Already Paid",
    "confidence": 72,
    "extracted_entities": {...},
    "reasoning": "..."
  },
  "action_plan": {
    "category": "Already Paid",
    "confidence": 72,
    "confidence_tier": "suggested",
    "pause_sequence": true,
    "notify": "finance",
    "action": "[SUGGESTED -- needs human confirmation] Request payment confirmation, then verify with finance",
    "followup_message": "Thank you for letting us know..."
  }
}
```

### `classify_dispute(transcript)` / `recommend_action(classification, invoice_ref)`
Lower-level tools, useful if you need to inspect or modify the classification
before deciding on an action (e.g., a custom routing rule for a specific
client).

## Interpreting `confidence_tier`

| Tier | Meaning | What to do |
|---|---|---|
| `auto` (confidence >= 80) | High confidence | Proceed with `action` automatically |
| `suggested` (50-79) | Moderate confidence | Surface to a human for one-click confirmation before acting |
| `needs_review` (< 50) | Low confidence | Route directly to human review queue; do not auto-act |

## Interpreting `notify`

| Value | Meaning |
|---|---|
| `null` | No escalation needed |
| `"finance"` | Client's finance team should verify a claim (payment/amount) |
| `"account_manager"` | Human account manager should take over this account |
| `"compliance"` | Highest priority -- fraud claim, pause everything |

## `pause_sequence`

If `true`, the automated outreach sequence for this account MUST be paused
immediately. Do not send further scheduled calls/emails until a human clears
the flag. This is non-negotiable for `Fraud Claim` and `Service Not Received`
-- continuing automation after those would be a brand-safety issue for the
client.

## Brand safety note

Any `followup_message` returned by this skill is written to be sent under the
CLIENT'S brand (white-label). It will never mention "AI", "agent",
"automation", or "AgentCollect" by name. If you need to customize tone per
client, that's a future extension point -- not currently parameterized.

## Example end-to-end flow

1. RetellAI call ends, transcript is captured
2. Standard pipeline checks: did the debtor agree to pay? If yes, proceed normally.
3. If debtor raised any objection -> call `resolve_dispute(transcript, invoice_ref)`
4. Check `action_plan.confidence_tier`:
   - `auto` -> execute `action_plan.action`, send `followup_message` if present
   - `suggested` -> queue for 1-click human confirmation
   - `needs_review` -> route to human review queue
5. If `action_plan.pause_sequence` is `true`, pause all scheduled outreach for this account
6. If `action_plan.notify` is set, create a task for the relevant team (finance / account_manager / compliance)