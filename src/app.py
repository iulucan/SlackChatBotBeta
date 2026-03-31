import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

BOT_TOKEN = "BOT_TOKEN"
APP_TOKEN = "APP_TOKEN"

app = App(token=BOT_TOKEN)


def normalize_text(text: str) -> str:
    return text.lower().strip()


def extract_amount(text: str):
    match = re.search(r"(\d+)\s*chf", text)
    if match:
        return int(match.group(1))
    return None


def extract_age(text: str):
    match = re.search(r"(\d+)\s*(years old|year old|yo\b|y/o\b)", text)
    if match:
        return int(match.group(1))
    return None

    # fallback patterns like "I am 52"
    match = re.search(r"\bi am (\d+)\b", text)
    if match:
        return int(match.group(1))
    return None


def is_security_question(text: str) -> bool:
    keywords = [
        "wifi",
        "wi-fi",
        "password",
        "guest password",
        "internal password",
        "mac address",
        "mac-address",
        "network access",
        "it credentials",
        "internal credentials",
    ]
    return any(keyword in text for keyword in keywords)


def answer_security_question() -> str:
    return (
        "I cannot provide internal Wi-Fi passwords, MAC address procedures, or other sensitive IT/security information in chat.\n"
        "Please contact Sarah Müller in IT for device registration or approved access procedures.\n"
        "Source: GreenLeaf Handbook, Section 6 (IT, Security & Connectivity)."
    )


def is_holiday_question(text: str) -> bool:
    holiday_terms = [
        "may 1",
        "may 1st",
        "1 may",
        "labor day",
        "is may 1 a holiday",
        "is may 1st a holiday",
        "do we work on may 1",
        "do we work on may 1st",
    ]
    return any(term in text for term in holiday_terms)


def answer_holiday_question() -> str:
    return (
        "Yes — May 1st is Labor Day and it is a full holiday for staff based in Basel-Stadt.\n"
        "Source: GreenLeaf Handbook, Section 4 (Time Off), and 2026 Holiday Logic CSV."
    )


def is_expense_question(text: str) -> bool:
    keywords = [
        "expense",
        "reimburse",
        "reimbursable",
        "lunch",
        "receipt",
        "client lunch",
    ]
    return any(keyword in text for keyword in keywords)


def answer_expense_question(text: str) -> str:
    amount = extract_amount(text)
    has_alcohol = "alcohol" in text
    has_client = (
        "with a client" in text
        or "with client" in text
        or "client is present" in text
        or "external client" in text
        or "a client is present" in text
    )
    no_client = (
        "without a client" in text
        or "without client" in text
        or "no client" in text
        or "without any client" in text
    )

    if has_alcohol:
        return (
            "No — alcohol is strictly non-reimbursable and must be paid on a separate personal receipt.\n"
            "Source: GreenLeaf Handbook, Section 7 (Expenses & Travel)."
        )

    if amount is not None and amount > 35:
        return (
            "No — the maximum allowed is 35 CHF per person.\n"
            "Source: GreenLeaf Handbook, Section 7 (Expenses & Travel)."
        )

    if no_client:
        return (
            "No — client lunches are only reimbursable if at least one external client is present.\n"
            "Source: GreenLeaf Handbook, Section 7 (Expenses & Travel)."
        )

    if has_client and amount is not None and amount <= 35:
        return (
            "Yes — this lunch can be reimbursed because it is at or under 35 CHF per person and includes at least one external client.\n"
            "Source: GreenLeaf Handbook, Section 7 (Expenses & Travel)."
        )

    return (
        "Please provide more details such as the amount in CHF, whether an external client is present, "
        "and whether alcohol is included.\n"
        "Example: Can I expense a 30 CHF lunch with a client?\n"
        "Source: GreenLeaf Handbook, Section 7 (Expenses & Travel)."
    )


def is_bereavement_question(text: str) -> bool:
    keywords = [
        "bereavement",
        "special leave",
        "death",
        "died",
        "funeral",
        "passed away",
        "leave if my",
        "can i stay home",
    ]
    return any(keyword in text for keyword in keywords)


def answer_bereavement_question(text: str) -> str:
    immediate_family_terms = ["spouse", "child", "parent", "mother", "father", "wife", "husband"]
    close_relative_terms = ["grandparent", "grandmother", "grandfather", "sibling", "brother", "sister"]

    if any(term in text for term in immediate_family_terms):
        return (
            "You are entitled to 3 days of paid leave for the death of a spouse, child, or parent.\n"
            "Any request exceeding 3 days requires a personal meeting and written approval from the CEO.\n"
            "Source: GreenLeaf Handbook, Section 5 (Bereavement & Special Leave)."
        )

    if any(term in text for term in close_relative_terms):
        return (
            "You are entitled to 1 day of paid leave for the death of a grandparent or sibling.\n"
            "Source: GreenLeaf Handbook, Section 5 (Bereavement & Special Leave)."
        )

    return (
        "I need the relationship to answer correctly.\n"
        "GreenLeaf policy states:\n"
        "- 3 paid days for spouse, child, or parent\n"
        "- 1 paid day for grandparent or sibling\n"
        "- More than 3 days requires a personal meeting and written approval from the CEO\n"
        "Source: GreenLeaf Handbook, Section 5 (Bereavement & Special Leave)."
    )


def is_vacation_question(text: str) -> bool:
    keywords = [
        "vacation",
        "annual leave",
        "holiday allowance",
        "days off",
        "paid leave per year",
        "how many days",
        "leave days",
    ]
    return any(keyword in text for keyword in keywords)


def answer_vacation_question(text: str) -> str:
    age = extract_age(text)

    if age is not None and age > 50:
        return (
            "You are entitled to 30 days of paid annual leave per calendar year: 25 standard days plus 5 additional days for employees over 50.\n"
            "Vacation requests must be submitted via the HR portal at least 3 weeks in advance, and Beat Müller handles final approvals.\n"
            "Source: GreenLeaf Handbook, Section 4 (Time Off)."
        )

    if age is not None and age <= 50:
        return (
            "You are entitled to 25 days of paid annual leave per calendar year.\n"
            "Vacation requests must be submitted via the HR portal at least 3 weeks in advance, and Beat Müller handles final approvals.\n"
            "Source: GreenLeaf Handbook, Section 4 (Time Off)."
        )

    if "over 50" in text or "older than 50" in text:
        return (
            "Employees over the age of 50 are entitled to 30 days of paid annual leave per calendar year: 25 standard days plus 5 additional days.\n"
            "Source: GreenLeaf Handbook, Section 4 (Time Off)."
        )

    return (
        "Full-time employees are entitled to 25 days of paid annual leave per calendar year. "
        "Employees over the age of 50 receive an additional 5 days.\n"
        "Vacation requests must be submitted via the HR portal at least 3 weeks in advance, and Beat Müller handles final approvals.\n"
        "Source: GreenLeaf Handbook, Section 4 (Time Off)."
    )


def answer_greeting(text: str):
    if text == "hi":
        return "Hello 👋"
    if "hello" in text:
        return "Hi 👋 I am GreenLeaf HR Bot!"
    return None


def fallback_answer() -> str:
    return (
        "I can help with GreenLeaf HR topics such as holidays, vacation allowance, bereavement leave, expense rules, and approved policy-based answers.\n"
        "Try asking:\n"
        "- Is May 1st a holiday?\n"
        "- Can I expense a 30 CHF lunch with a client?\n"
        "- How many vacation days do employees over 50 get?\n"
        "- How many bereavement leave days do I get if my parent died?"
    )


@app.message("")
def handle_message(message, say):
    text = normalize_text(message.get("text", ""))

    print("Received:", text)

    greeting_answer = answer_greeting(text)
    if greeting_answer:
        say(greeting_answer)
        return

    if is_security_question(text):
        say(answer_security_question())
        return

    if is_holiday_question(text):
        say(answer_holiday_question())
        return

    if is_expense_question(text):
        say(answer_expense_question(text))
        return

    if is_bereavement_question(text):
        say(answer_bereavement_question(text))
        return

    if is_vacation_question(text):
        say(answer_vacation_question(text))
        return

    if "how are you" in text:
        say("I am doing well, thank you! 👋")
        return

    say(fallback_answer())


if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()# Slack Bolt interface — handles incoming messages
