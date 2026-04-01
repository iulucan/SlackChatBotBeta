"""
app.py — GreenLeaf Bot | Slack Interface Layer
================================================
This is the entry point for the GreenLeaf HR Assistant bot.

Architecture (HLD):
    Slack (employee) → app.py → privacy_gate.py → brain.py → tools
                                      ↓
                              blocks sensitive queries
                              (Wi-Fi, salary, MAC address)

Tech stack:
    - Slack Bolt for Python (Socket Mode) — no public server needed
    - python-dotenv — loads tokens from .env file
    - privacy_gate.py — security filter (PII + injection blocking)

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


def process_query(raw_query, say):
    """Shared logic for DM messages and channel mentions."""
    query = clean_input(raw_query)

    if is_blocked(query):
        say(get_block_message(query))
        return

    say(f"✅ Got your message: _{query}_\n> Privacy gate: passed\n> Brain: coming in Week 3!")


@app.message("")
def handle_message(message, say):
    """Handles direct messages to the bot."""
    raw_query = message.get("text", "")
    process_query(raw_query, say)


@app.event("app_mention")
def handle_mention(event, say):
    """Handles @GreenLeaf mentions in channels."""
    raw_query = event.get("text", "")
    process_query(raw_query, say)


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
#    # Edit .env and add your tokens:
#    # SLACK_BOT_TOKEN=os.environ["SLACK_BOT_TOKEN"]
#    # SLACK_APP_TOKEN=os.environ["SLACK_APP_TOKEN"]
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
#    "What is the wifi password?"  → should be BLOCKED
#    "What is my salary?"          → should be BLOCKED
#    "Is May 1st a holiday?"       → should PASS (brain coming Week 3)
# =============================================================================
