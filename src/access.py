from __future__ import annotations

from src.config import get_setting

def configured_admin_emails() -> set[str]:
    raw_emails = get_setting("ADMIN_EMAILS")
    return {email.strip().lower() for email in raw_emails.split(",") if email.strip()}


def is_admin_email(email: str | None) -> bool:
    return bool(email) and email.strip().lower() in configured_admin_emails()
