# Slack Bolt interface — handles incoming messages via Socket Mode

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from src.privacy_gate import is_blocked, get_block_message

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.message("")
def handle_message(message, say):
    query = message.get("text", "")

    # Step 1 — Privacy gate check
    if is_blocked(query):
        say(get_block_message(query))
        return

    # Step 2 — Placeholder (brain.py coming Week 3)
    say(f"✅ Got your message: _{query}_\n> Privacy gate: passed\n> Brain: coming in Week 3!")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡ GreenLeaf Bot is running...")
    handler.start()
