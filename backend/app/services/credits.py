from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.admin_access import has_unlimited_credits
from app.models import CreditBalance, CreditTransaction, User


def get_balance(db: Session, user_id: int) -> int:
    row = db.get(CreditBalance, user_id)
    return row.balance if row else 0


def ensure_balance_row(db: Session, user: User, initial: int = 0) -> CreditBalance:
    row = db.get(CreditBalance, user.id)
    if row is None:
        row = CreditBalance(user_id=user.id, balance=initial)
        db.add(row)
        db.flush()
    return row


def apply_credit_change(
    db: Session,
    user: User,
    amount: int,
    reason: str,
    *,
    reference_type: str | None = None,
    reference_id: str | None = None,
    allow_negative: bool = False,
) -> CreditBalance:
    if amount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kredi miktarı 0 olamaz",
        )

    balance = ensure_balance_row(db, user, initial=0)

    # Admin: harcama düşülmez (sonsuz kredi)
    if amount < 0 and has_unlimited_credits(user):
        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=0,
                reason=f"[admin ∞] {reason}",
                reference_type=reference_type,
                reference_id=reference_id,
            )
        )
        db.flush()
        return balance

    new_balance = balance.balance + amount

    if new_balance < 0 and not allow_negative:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Yetersiz kredi. Mevcut: {balance.balance}, gereken: {abs(amount)}",
        )

    balance.balance = new_balance
    balance.updated_at = datetime.now(timezone.utc)

    db.add(
        CreditTransaction(
            user_id=user.id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )
    db.flush()
    return balance
