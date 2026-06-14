from src.db.client import get_client


def get_categories(user_id: str, category_type: str) -> list[dict]:
    result = (
        get_client()
        .table("categories")
        .select("id, name, type")
        .eq("user_id", user_id)
        .eq("type", category_type)
        .order("name")
        .execute()
    )
    return result.data or []


def get_category_by_id(user_id: str, category_id: str) -> dict | None:
    result = (
        get_client()
        .table("categories")
        .select("id, name, type")
        .eq("id", category_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def add_category(user_id: str, name: str, category_type: str) -> dict | None:
    """Returns the new category dict, or None if the name already exists."""
    sb = get_client()
    existing = (
        sb.table("categories")
        .select("id")
        .eq("user_id", user_id)
        .eq("name", name)
        .eq("type", category_type)
        .limit(1)
        .execute()
    )
    if existing.data:
        return None
    result = sb.table("categories").insert({
        "user_id": user_id,
        "name": name,
        "type": category_type,
    }).execute()
    return result.data[0]


def remove_category(user_id: str, category_id: str) -> None:
    # Budget cascade-deletes via FK ON DELETE CASCADE
    get_client().table("categories").delete().eq("id", category_id).eq("user_id", user_id).execute()
