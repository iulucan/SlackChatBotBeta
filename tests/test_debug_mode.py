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
    # ── English ──────────────────────────────────────────────────────────
    "I'm Hans, how many vacation days do I get? --debug/extended",
    "Is May 1st a holiday in Basel? --debug/extended",
    "Can I expense a 40 CHF client lunch? --debug/extended",
    "My grandmother passed away, how many days off do I get? --debug/extended",
    "Is January 1st a holiday in Zurich? --debug/extended",
    "I have a problem with my manager. What should i do? --debug/extended",
    "Fire emergency in the office --debug/extended",
    "Family emergency --debug/extended",
    "Company history --debug/extended",
    # ── French ───────────────────────────────────────────────────────────
    "Est-ce que le 1er mai est un jour férié à Genève? --debug/extended",       # holiday → GE
    "Puis-je rembourser un déjeuner client de 30 CHF? --debug/extended",        # expense → under limit
    "Combien de jours de congé ai-je par an? --debug/extended",                 # policy → vacation
    "Ma grand-mère est décédée, combien de jours de congé ai-je? --debug/extended",  # policy → bereavement
    "J'ai un problème avec mon collègue. Que dois-je faire? --debug/extended",  # policy → wellbeing
    # ── German ───────────────────────────────────────────────────────────
    "Ist der 1. August ein Feiertag in Zürich? --debug/extended",               # holiday → ZH
    "Kann ich ein Mittagessen von 50 CHF abrechnen? --debug/extended",          # expense → over limit
    "Wie viele Urlaubstage habe ich pro Jahr? --debug/extended",                # policy → vacation
    "Meine Großmutter ist gestorben, wie viele Tage bekomme ich frei? --debug/extended",  # policy → bereavement
    "Es gibt einen Feueralarm im Büro. Was soll ich tun? --debug/extended",     # policy → safety
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
    t_translate_query = time.time()
    query_in_english = translate_text(query, "en", user_lang)
    t_translate_query_done = round(time.time() - t_translate_query, 2)

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
        dbg = result.get("debug", {})
        t = dbg.get("timings", result.get("timings", {}))
        retries = dbg.get("retries", {})
        cache = dbg.get("cache", {})

        def _ann(step):
            r = retries.get(step)
            if r and r.get("count"):
                n = r["count"]
                return f"  ⚠️ {n} retr{'y' if n == 1 else 'ies'} — {r['reason']}"
            c = cache.get(step)
            return f"  (cache: {c})" if c else ""

        dm = dbg.get("dispatch_meta") or {}
        dispatch_sub = ""
        if dm.get("policy_type"):
            dispatch_sub += f"\n    Policy type:     {dm['policy_type']}"
        if dm.get("emergency"):
            dispatch_sub += f"\n    Emergency:       {dm['emergency']}"
        if dm.get("role_required"):
            dispatch_sub += f"\n    Role required:   {dm['role_required']}"

        translate_query_line = (
            f"\n  Translate query:   {t_translate_query_done}s"
            if user_lang != "en" else ""
        )
        final_text += (
            f"\n\n```[DEBUG EXTENDED]"
            f"\n  Language:          {dbg.get('lang', '—')}"
            f"\n  Intent:            {dbg.get('intent', '—')}"
            f"\n  ─────────────────────────────"
            f"{translate_query_line}"
            f"\n  Intent classify:   {t.get('classify', '—')}s{_ann('classify')}"
            f"\n  Tool dispatch:     {t.get('dispatch', '—')}s{_ann('dispatch')}{dispatch_sub}"
            f"\n  Translate answer:  {t.get('translate', '—')}s{_ann('translate')}"
            f"\n  ─────────────────────────────"
            f"\n  Total:             {elapsed}s  |  🛠 {tool_label}```"
        )

    say(final_text)


if __name__ == "__main__":
    print(f"\nDEBUG_MODE = {DEBUG_MODE}")
    print("Running Steel Thread Demo emulation...\n")
    for prompt in TEST_PROMPTS:
        emulate(prompt)
