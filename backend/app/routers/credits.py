from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_admin_user, get_current_user
from app.models import CreditTransaction, User
from app.schemas import CreditAdjust, CreditBalanceOut, CreditTransactionOut, PricingOut
from app.services.credits import apply_credit_change, ensure_balance_row
from app.services.pricing import pricing_dict

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/pricing", response_model=PricingOut)
def get_pricing() -> PricingOut:
    """Herkese açık fiyat tablosu (giriş gerekmez)."""
    return PricingOut(**pricing_dict())


@router.get("", response_model=CreditBalanceOut)
def get_credits(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreditBalanceOut:
    row = ensure_balance_row(db, user, initial=0)
    db.commit()
    return CreditBalanceOut(balance=row.balance, updated_at=row.updated_at)


@router.get("/transactions", response_model=list[CreditTransactionOut])
def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CreditTransaction]:
    stmt = (
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.post("/adjust", response_model=CreditBalanceOut)
def adjust_credits(
    payload: CreditAdjust,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> CreditBalanceOut:
    """Yalnızca admin — kendi test bakiyesini ayarlar. Kullanıcı kredisi için /admin/users/{id}/credits."""
    balance = apply_credit_change(
        db,
        admin,
        payload.amount,
        payload.reason,
        reference_type=payload.reference_type or "admin_self_adjust",
        reference_id=payload.reference_id,
        allow_negative=False,
    )
    db.commit()
    db.refresh(balance)
    return CreditBalanceOut(balance=balance.balance, updated_at=balance.updated_at)
