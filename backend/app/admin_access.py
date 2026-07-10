from app.config import get_settings
from app.models import User


def is_admin(user: User) -> bool:
    """ADMIN_EMAIL ile eşleşen tek kullanıcı admin sayılır."""
    admin_email = (get_settings().admin_email or "").strip().lower()
    if not admin_email:
        return False
    return user.email.lower() == admin_email


def has_unlimited_credits(user: User) -> bool:
    return is_admin(user)
