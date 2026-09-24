from __future__ import annotations

from src.config import get_setting


def is_logged_in(user) -> bool:
    try:
        return bool(user.get("is_logged_in", False))
    except (AttributeError, TypeError):
        return bool(getattr(user, "is_logged_in", False))


def user_email(user) -> str | None:
    try:
        email = user.get("email")
    except (AttributeError, TypeError):
        email = getattr(user, "email", None)
    return str(email) if email else None


def configured_admin_emails() -> set[str]:
    raw_emails = get_setting("ADMIN_EMAILS")
    return {email.strip().lower() for email in raw_emails.split(",") if email.strip()}


def is_admin_email(email: str | None) -> bool:
    return bool(email) and email.strip().lower() in configured_admin_emails()
