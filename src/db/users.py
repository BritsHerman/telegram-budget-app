from src.db.client import get_client


def get_or_create_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict:
    sb = get_client()
    result = (
        sb.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]
    new = sb.table("users").insert({
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
    }).execute()
    return new.data[0]


def resolve_user(from_user) -> dict:
    """Get or create a user record from a Telegram User object."""
    return get_or_create_user(
        telegram_id=from_user.id,
        username=from_user.username,
        first_name=from_user.first_name,
        last_name=from_user.last_name,
    )


def set_budget_day(user_id: str, day: int) -> None:
    get_client().table("users").update({"budget_day": day}).eq("id", user_id).execute()
