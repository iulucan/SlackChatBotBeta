"""
test_debug_mode.py — Local terminal emulator for Slack debug output
====================================================================
Simulates exactly what the bot sends to Slack, but prints to terminal.
Run: python tests/test_debug_mode.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.privacy_gate import clean_input, is_blocked, get_block_message
from src.brain import respond

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
TOOL_LABELS = {
    "policy_tool":  "RAG (ChromaDB / FAISS)",
    "holiday_tool": "API (OpenHolidays)",
    "expense_tool": "Logic (Rules Engine)",
    "unknown":      "Unknown",
}

TEST_PROMPTS = [
    "I'm Hans, how many vacation days do I get?",
    "Is May 1st a holiday in Basel?",
    "Can I expense a 40 CHF client lunch?",
    "My grandmother passed away, how many days off do I get?",
]

def say(msg):
    print(msg)

def emulate(raw_query):
    print("\n" + "="*60)
    print(f"USER: {raw_query}")
    print("="*60)

    t_start = time.time()

    if is_blocked(raw_query):
        say(get_block_message(raw_query))
        return

    query = clean_input(raw_query)
    pii_masked = query != raw_query

    if is_blocked(query):
        say(get_block_message(query))
        return

    result, tool_used = respond(query)

    if "error" in result:
        say("Sorry, I could not find an answer. Please contact HR directly.")
        return

    say(f"{result['answer']}\n\n_Source: {result['source']}_")

    if DEBUG_MODE:
        pii_flag = "🔒 PII masked  |  " if pii_masked else ""
        tool_label = TOOL_LABELS.get(tool_used, tool_used)
        elapsed = round(time.time() - t_start, 2)
        say(f"```[DEBUG]  {pii_flag}🛠 Tool: {tool_label}  |  ⏱ {elapsed}s```")


if __name__ == "__main__":
    print(f"\n🟢 DEBUG_MODE = {DEBUG_MODE}")
    print("Running Steel Thread Demo emulation...\n")
    for prompt in TEST_PROMPTS:
        emulate(prompt)
