import json
import os
from typing import Dict

USERS_FILE = "users.json"


# ────────────────────────── helpers ──────────────────────────
def _read_json() -> Dict[str, dict]:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(data: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─────────────────────── public interface ────────────────────
def load_users() -> Dict[str, dict]:
    return _read_json()


def save_users(data: dict) -> None:
    _write_json(data)


def add_user_if_not_exists(user_id: int, first_name: str, username: str | None):
    users = load_users()
    uid = str(user_id)

    if uid not in users:
        users[uid] = {"first_name": first_name, "username": username}
        save_users(users)


def get_user_display(user_id: int) -> str:
    """
    Повертає зручний рядок для відображення користувача:
    • «Ім’я (@username)»  
    • або «Ім’я»  
    • або «ID: 123»
    """
    user = load_users().get(str(user_id))
    if not user:
        return f"ID: {user_id}"

    first_name = user.get("first_name", "")
    username = user.get("username", "")
    if username:
        return f"{first_name} (@{username})".strip()
    return first_name or f"ID: {user_id}"
