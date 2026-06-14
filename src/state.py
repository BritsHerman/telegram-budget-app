from typing import Any

# Keyed by chat_id (== telegram_user_id in private chats).
# Tracks pending reply prompts so we know what to do with the user's next message.
awaiting_reply: dict[int, dict[str, Any]] = {}
