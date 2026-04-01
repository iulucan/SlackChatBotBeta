"""
app.py — GreenLeaf Bot | Slack Interface Layer
================================================
Entry point for the GreenLeaf HR Assistant bot.

Architecture (HLD):
    Slack (employee) → app.py → clean_input() → is_blocked() → brain.py → tools

Message flow:
    1. Receive message from Slack
    2. Mask PII via clean_input() — names, IDs, emails
    3. Check security via is_blocked() — Wi-Fi, salary, injection
    4. Route to brain.py (Week 3)

Tech stack:
    - Slack Bolt for Python (Socket Mode)
    - python-dotenv — loads tokens from .env
    - privacy_gate.py — PII masking + security filter

Sprint: Week 2 | Owner: Ibrahim (System Architect)
"""

import os
import sys

# Add project root to Python path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from src.privacy_gate import clean_input, is_blocked, get_block_message

# Load tokens from .env file (never hardcode tokens in code)
load_dotenv()

# Initialize Slack app with bot token
app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.message("")
def handle_message(message, say):
    """
    Handles all incoming Slack messages.

    Flow:
        1. clean_input()  — mask PII (names, IDs, emails)
        2. is_blocked()   — refuse sensitive or injected queries
        3. brain.py       — route to correct tool (Week 3)
    """
    raw_query = message.get("text", "")

    # Step 1 — Mask PII before any processing
    # Original text is never logged or forwarded
    query = clean_input(raw_query)

    # Step 2 — Block sensitive queries and prompt injection
    if is_blocked(query):
        say(get_block_message(query))
        return

    # Step 3 — Brain router (coming Week 3)
    # Will route to: policy_tool, holiday_tool, or expense_tool
    say(f"✅ Got your message: _{query}_\n> Privacy gate: passed\n> Brain: coming in Week 3!")


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡ GreenLeaf Bot is running...")
    handler.start()


# =============================================================================
# HOW TO TEST LOCALLY
# =============================================================================
#
# 1. Create your Slack App at https://api.slack.com/apps
#    - Enable Socket Mode → generate App Token (os.environ["SLACK_APP_TOKEN"]...)
#    - OAuth & Permissions → add scopes: chat:write, im:history, app_mentions:read
#    - Event Subscriptions → enable: message.im, app_mention
#    - App Home → enable "Allow users to send messages"
#    - Install to Workspace → copy Bot Token (os.environ["SLACK_BOT_TOKEN"]...)
#
# 2. Set up environment:
#    cp .env.example .env
#    # Edit .env and add your tokens
#
# 3. Install dependencies:
#    python -m venv venv
#    source venv/bin/activate
#    pip install -r requirements.txt
#
# 4. Fix SSL certificates (macOS only, one-time):
#    /Applications/Python\ 3.10/Install\ Certificates.command
#
# 5. Run the bot:
#    python src/app.py
#
# 6. Test in Slack (DM the bot):
#    "My name is Beat Müller"       → bot sees: "My name is [NAME]"
#    "My ID is 12345"               → bot sees: "My ID is [ID]"
#    "What is the wifi password?"   → BLOCKED
#    "Ignore previous instructions" → BLOCKED (injection)
#    "Is May 1st a holiday?"        → PASSED
# =============================================================================
