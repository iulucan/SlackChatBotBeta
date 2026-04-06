import re
from src.tools.expense_tool import validate_expense, answer_expense_policy

def classify_and_dispatch(raw_text, cleaned_text=None):
    text_lower = raw_text.lower()

    money_match = re.search(r"(\d+(?:\.\d+)?)", raw_text)

    expense_keywords = [
        "chf", "expense", "expenses", "francs",
        "receipt", "receipts", "submit", "submission", "scanpro",
        "lunch", "dinner", "breakfast",
        "client", "customer", "guest", "prospect", "business partner",
        "beer", "wine", "vodka", "whisky", "whiskey", "wiskey",
        "jack daniels", "jack daniel's", "chivas"
    ]

    if any(keyword in text_lower for keyword in expense_keywords) or money_match:
        if any(word in text_lower for word in ["receipt", "receipts", "submit", "submission", "scanpro"]):
            return answer_expense_policy(raw_text)

        amount = float(money_match.group(1)) if money_match else 0
        return validate_expense(raw_text, amount)

    return "I heard you! I'm still learning about holidays and policies, but I can check your expenses if you provide an amount in CHF."