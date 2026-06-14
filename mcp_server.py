"""
mcp_server.py

MCP (Model Context Protocol) server exposing AgentCollect's dispute
classification and routing pipeline as tools that Claude Code (or any
MCP-compatible client) can call directly.

Exposed tools:
  - classify_dispute(transcript)   -> classification result
  - recommend_action(classification, invoice_ref) -> action plan
  - resolve_dispute(transcript, invoice_ref) -> full pipeline (classify + recommend)

Run with:
    python3 mcp_server.py

This uses stdio transport, the standard for local MCP servers used by
Claude Code / Claude Desktop.
"""

import json
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from classifier import classify_transcript, DISPUTE_CATEGORIES
from action_engine import recommend_action


server = Server("agentcollect-dispute-resolver")


# --------------------------------------------------------------------------
# Tool definitions
# --------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="classify_dispute",
            description=(
                "Classify a dispute raised by a debtor during an AgentCollect "
                "recovery call/email. Returns category, confidence score, "
                "extracted entities (payment dates, reference numbers, etc.), "
                f"and reasoning. Categories: {', '.join(DISPUTE_CATEGORIES)}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transcript": {
                        "type": "array",
                        "description": (
                            "List of conversation turns, each with 'role' "
                            "('agent' or 'debtor') and 'content' (string)."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                    },
                },
                "required": ["transcript"],
            },
        ),
        Tool(
            name="recommend_action",
            description=(
                "Given a classification result (from classify_dispute), "
                "return an action plan: whether to pause the outreach "
                "sequence, who to notify (finance/account_manager/compliance), "
                "the recommended action, and -- if evidence is needed -- a "
                "brand-safe follow-up message to send the debtor."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "classification": {
                        "type": "object",
                        "description": "Output of classify_dispute (category, confidence, extracted_entities, reasoning).",
                    },
                    "invoice_ref": {
                        "type": "string",
                        "description": "Invoice reference (e.g. '#4821'), used in generated messages.",
                    },
                },
                "required": ["classification"],
            },
        ),
        Tool(
            name="resolve_dispute",
            description=(
                "Full pipeline: classify a dispute transcript AND generate "
                "an action plan in one call. This is the recommended entry "
                "point for most use cases -- combines classify_dispute + "
                "recommend_action."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transcript": {
                        "type": "array",
                        "description": "List of conversation turns (role + content).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                    },
                    "invoice_ref": {
                        "type": "string",
                        "description": "Invoice reference (e.g. '#4821'), used in generated messages.",
                    },
                },
                "required": ["transcript"],
            },
        ),
    ]


# --------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "classify_dispute":
        transcript = arguments["transcript"]
        result = classify_transcript(transcript)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "recommend_action":
        classification = arguments["classification"]
        invoice_ref = arguments.get("invoice_ref", "this invoice")
        result = recommend_action(classification, invoice_ref=invoice_ref)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "resolve_dispute":
        transcript = arguments["transcript"]
        invoice_ref = arguments.get("invoice_ref", "this invoice")

        classification = classify_transcript(transcript)
        plan = recommend_action(classification, invoice_ref=invoice_ref)

        combined = {
            "classification": classification,
            "action_plan": plan,
        }
        return [TextContent(type="text", text=json.dumps(combined, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())