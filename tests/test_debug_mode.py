"""
test_debug_mode.py — Local terminal emulator for Slack debug output
====================================================================
Simulates exactly what the bot sends to Slack, but prints to terminal.
Run: python tests/test_debug_mode.py
"""

import os
import sys
import time
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import py3langid as langid
langid.set_languages(['de', 'en', 'fr', 'it'])

from src.privacy_gate import clean_input, is_blocked, get_block_message
from src.brain import respond, translate_text
from src.it_security_handler import is_it_security_query

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
    "Is May 1st a holiday in Basel? --debug/compact",
    "Can I expense a 40 CHF client lunch? --debug/extended",
]

def say(msg):
    print(msg)

def emulate(raw_query):
    print("\n" + "="*60)
    print(f"USER: {raw_query}")
    print("="*60)

    t_start = time.time()

    # Detect debug flag — READ ONLY, raw_query not modified yet
    if "--debug/extended" in raw_query:
        debug_level = "extended"
    elif "--debug/compact" in raw_query:
        debug_level = "compact"
    elif DEBUG_MODE:
        debug_level = "compact"
    else:
        debug_level = None

    # Security checks see the FULL original query including any debug flag
    is_it, it_response = is_it_security_query(raw_query)
    if is_it:
        say(it_response)
        return

    is_raw_blocked, _ = is_blocked(raw_query)
    if is_raw_blocked:
        say(get_block_message(raw_query))
        return

    # Strip flag only after security checks have passed
    if debug_level in ("compact", "extended"):
        raw_query = raw_query.replace("--debug/extended", "").replace("--debug/compact", "").strip()

    query = clean_input(raw_query)

    is_masked_blocked, _ = is_blocked(query)
    if is_masked_blocked:
        say(get_block_message(query))
        return

    lang, _ = langid.classify(query)
    user_lang = lang if lang in ("de", "en", "fr", "it") else "en"
    query_in_english = translate_text(query, "en", user_lang)

    result, tool_used = respond(query_in_english, user_lang)

    if "error" in result:
        say("Sorry, I could not find an answer. Please contact HR directly.")
        return

    final_text = f"{result['answer']}\n\n_Source: {result['source']}_"

    if debug_level == "compact":
        tool_label = TOOL_LABELS.get(tool_used, tool_used)
        elapsed = round(time.time() - t_start, 2)
        final_text += f"\n\n```[DEBUG]  🛠 Tool: {tool_label}  |  ⏱ {elapsed}s```"
    elif debug_level == "extended":
        tool_label = TOOL_LABELS.get(tool_used, tool_used)
        elapsed = round(time.time() - t_start, 2)
        t = result.get("timings", {})
        final_text += (
            f"\n\n```[DEBUG EXTENDED]"
            f"\n  Intent classify:   {t.get('classify', '—')}s"
            f"\n  Tool dispatch:     {t.get('dispatch', '—')}s"
            f"\n  Translate answer:  {t.get('translate', '—')}s"
            f"\n  ─────────────────────────"
            f"\n  Total:             {elapsed}s  |  🛠 {tool_label}```"
        )

    say(final_text)


if __name__ == "__main__":
    print(f"\nDEBUG_MODE = {DEBUG_MODE}")
    print("Running Steel Thread Demo emulation...\n")
    for prompt in TEST_PROMPTS:
        emulate(prompt)
