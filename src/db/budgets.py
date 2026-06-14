from src.db.client import get_client


def get_budget(user_id: str, category_id: str) -> float | None:
    result = (
        get_client()
        .table("budgets")
        .select("amount")
        .eq("user_id", user_id)
        .eq("category_id", category_id)
        .limit(1)
        .execute()
    )
    return float(result.data[0]["amount"]) if result.data else None


def get_all_budgets(user_id: str) -> list[dict]:
    result = (
        get_client()
        .table("budgets")
        .select("id, amount, categories(id, name, type)")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def get_expense_budgets(user_id: str) -> list[dict]:
    budgets = get_all_budgets(user_id)
    return [b for b in budgets if b["categories"]["type"] == "expense"]


def set_budget(user_id: str, category_id: str, amount: float) -> None:
    sb = get_client()
    if amount == 0:
        sb.table("budgets").delete().eq("user_id", user_id).eq("category_id", category_id).execute()
    else:
        sb.table("budgets").upsert(
            {"user_id": user_id, "category_id": category_id, "amount": amount},
            on_conflict="user_id,category_id",
        ).execute()
