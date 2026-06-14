from typing import Any

# Keyed by chat_id (== telegram_user_id in private chats).
# Tracks pending reply prompts so we know what to do with the user's next message.
awaiting_reply: dict[int, dict[str, Any]] = {}

# Tracks the message_id of the last menu message sent to each user so we can
# strip its buttons when a new menu is sent, keeping the chat clean.
last_menu_message_id: dict[int, int] = {}
