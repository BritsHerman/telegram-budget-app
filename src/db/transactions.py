from datetime import datetime

from src.db.client import get_client


def add_transaction(user_id: str, category_id: str, amount: float, tx_type: str) -> dict:
    result = get_client().table("transactions").insert({
        "user_id": user_id,
        "category_id": category_id,
        "amount": amount,
        "type": tx_type,
    }).execute()
    return result.data[0]


def delete_transaction(user_id: str, transaction_id: str) -> bool:
    result = (
        get_client()
        .table("transactions")
        .delete()
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def get_spent_amount(user_id: str, category_id: str, start: datetime, end: datetime) -> float:
    result = (
        get_client()
        .table("transactions")
        .select("amount")
        .eq("user_id", user_id)
        .eq("category_id", category_id)
        .gte("transacted_at", start.isoformat())
        .lte("transacted_at", end.isoformat())
        .execute()
    )
    return sum(float(r["amount"]) for r in (result.data or []))


def get_expense_transactions_for_period(
    user_id: str, start: datetime, end: datetime
) -> list[dict]:
    result = (
        get_client()
        .table("transactions")
        .select("amount, categories(name)")
        .eq("user_id", user_id)
        .eq("type", "expense")
        .gte("transacted_at", start.isoformat())
        .lte("transacted_at", end.isoformat())
        .execute()
    )
    return result.data or []


def get_income_transactions_for_period(
    user_id: str, start: datetime, end: datetime
) -> list[dict]:
    result = (
        get_client()
        .table("transactions")
        .select("amount, categories(name)")
        .eq("user_id", user_id)
        .eq("type", "income")
        .gte("transacted_at", start.isoformat())
        .lte("transacted_at", end.isoformat())
        .execute()
    )
    return result.data or []


def get_all_transactions_for_period(
    user_id: str, start: datetime, end: datetime
) -> list[dict]:
    result = (
        get_client()
        .table("transactions")
        .select("id, amount, type, transacted_at, categories(name)")
        .eq("user_id", user_id)
        .gte("transacted_at", start.isoformat())
        .lte("transacted_at", end.isoformat())
        .order("transacted_at", desc=True)
        .execute()
    )
    return result.data or []


def get_recent_transactions(user_id: str, limit: int = 10) -> list[dict]:
    result = (
        get_client()
        .table("transactions")
        .select("id, amount, type, transacted_at, categories(name)")
        .eq("user_id", user_id)
        .order("transacted_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
