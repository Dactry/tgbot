from __future__ import annotations

import json
import os
from collections import OrderedDict
from datetime import datetime, date

DATA_FILE = "data.json"


# ────────────────────────── helpers ──────────────────────────
def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _purge_past_dates(data: dict) -> dict:
    """
    Видаляє дні, що вже минули (порівнюється з поточною датою).
    Повертає очищений словник.
    """
    today = date.today()
    for d in list(data.keys()):
        try:
            d_date = datetime.strptime(d, "%Y-%m-%d").date()
            if d_date < today:
                data.pop(d)
        except ValueError:
            # ключ не у форматі YYYY-MM-DD — лишаємо, раптом щось інше
            pass
    return data


# ───────────────────── public API (data) ─────────────────────
def load_data() -> dict:
    """
    Читає `data.json`, прибирає минулі дати
    й одразу зберігає файл, якщо щось змінилось.
    """
    data = _read_json(DATA_FILE)
    cleaned = _purge_past_dates(data)
    if cleaned != data:
        _write_json(DATA_FILE, cleaned)
    return cleaned


def save_data(data: dict) -> None:
    """Зберігає дані, відсортовані за датою та часом."""
    ordered: dict[str, dict[str, int]] = OrderedDict()
    for d in sorted(data.keys()):
        ordered[d] = OrderedDict(
            sorted(
                data[d].items(),
                key=lambda kv: datetime.strptime(kv[0], "%H:%M"),
            )
        )
    _write_json(DATA_FILE, ordered)


# ──────────────────── booking core functions ─────────────────
def is_slot_available(date_str: str, time: str) -> bool:
    """Перевіряє, чи вільний слот *HH:MM* на дату *YYYY-MM-DD*."""
    data = load_data()
    return time not in data.get(date_str, {})


def book_slot(date_str: str, time: str, user_id: int) -> bool:
    """
    Бронює слот. Повертає *True*, якщо вдалося, *False* — якщо зайнятий.
    У файлі зберігаємо лише `user_id` (INT).
    """
    data = load_data()
    if not is_slot_available(date_str, time):
        return False

    data.setdefault(date_str, {})[time] = user_id
    save_data(data)
    return True


def cancel_slot(
    date_str: str,
    time: str,
    requester_id: int,
    *,
    is_admin: bool = False,
) -> int | None:
    """
    Скасовує бронювання й повертає **id користувача, чиє бронювання було видалено**,
    або *None*, якщо скасувати не вдалося.

    • Звичайний користувач може скасувати лише власні бронювання.  
    • Адміністратор (is_admin=True) — будь-які.
    """
    data = load_data()
    user_entry = data.get(date_str, {}).get(time)
    if user_entry is None:
        return None

    booked_uid = user_entry["id"] if isinstance(user_entry, dict) else int(user_entry)
    if not (is_admin or booked_uid == requester_id):
        return None  # недостатньо прав

    # видаляємо слот
    del data[date_str][time]
    if not data[date_str]:
        del data[date_str]

    save_data(data)
    return booked_uid
