"""
server.py

Small local backend that proxies requests from dashboard.html to the
Anthropic API, using your ANTHROPIC_API_KEY from the environment.

This exists because browsers can't call api.anthropic.com directly with a
secret key (CORS + security) -- the dashboard calls THIS server instead,
and this server calls Claude.

Run:
    pip install flask flask-cors anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python server.py

Then open dashboard.html in your browser (it calls http://localhost:5000).
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)  # allow dashboard.html (opened as a local file) to call this server

client = Anthropic()  # reads ANTHROPIC_API_KEY from environment


@app.route("/api/claude", methods=["POST"])
def claude_proxy():
    """
    Expects JSON body:
        {
          "system": "<system prompt>",
          "prompt": "<user message>",
          "max_tokens": 500
        }

    Returns:
        { "text": "<claude's response text>" }
    """
    data = request.get_json()

    system_prompt = data.get("system", "")
    user_prompt = data.get("prompt", "")
    max_tokens = data.get("max_tokens", 500)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text
        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY is not set. The dashboard will get errors.")
        print("Run: export ANTHROPIC_API_KEY='sk-ant-...'  (Mac/Linux)")
        print("  or: $env:ANTHROPIC_API_KEY='sk-ant-...'    (Windows PowerShell)")

    app.run(port=5000, debug=True)