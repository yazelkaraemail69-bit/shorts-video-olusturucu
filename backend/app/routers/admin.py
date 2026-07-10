from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin_access import has_unlimited_credits, is_admin
from app.database import get_db
from app.deps import get_admin_user
from app.models import CreditBalance, Scenario, User, VideoJob
from app.schemas import (
    AdminCreditGrant,
    AdminStatsOut,
    AdminUserOut,
    AdminUserUpdate,
    CreditBalanceOut,
    MessageOut,
)
from app.services.credits import apply_credit_change, ensure_balance_row, get_balance

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(db: Session, user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_admin=is_admin(user),
        credits=get_balance(db, user.id),
        unlimited_credits=has_unlimited_credits(user),
        created_at=user.created_at,
    )


@router.get("/stats", response_model=AdminStatsOut)
def stats(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> AdminStatsOut:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    active = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    scenarios = db.scalar(select(func.count()).select_from(Scenario)) or 0
    jobs = db.scalar(select(func.count()).select_from(VideoJob)) or 0
    return AdminStatsOut(users=users, active_users=active, scenarios=scenarios, jobs=jobs)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [_user_out(db, u) for u in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı yok")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendi hesabınızı pasifleştiremezsiniz",
        )
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return _user_out(db, user)


@router.post("/users/{user_id}/credits", response_model=CreditBalanceOut)
def grant_credits(
    user_id: int,
    payload: AdminCreditGrant,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> CreditBalanceOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı yok")
    if has_unlimited_credits(user) and payload.amount < 0:
        ensure_balance_row(db, user)
        db.commit()
        bal = db.get(CreditBalance, user.id)
        return CreditBalanceOut(balance=bal.balance if bal else 0, updated_at=bal.updated_at if bal else None)

    balance = apply_credit_change(
        db,
        user,
        payload.amount,
        payload.reason,
        reference_type="admin_grant",
        reference_id=str(_admin.id),
        allow_negative=True,
    )
    db.commit()
    db.refresh(balance)
    return CreditBalanceOut(balance=balance.balance, updated_at=balance.updated_at)


@router.get("/ping", response_model=MessageOut)
def ping(_admin: User = Depends(get_admin_user)) -> MessageOut:
    return MessageOut(detail="admin ok")
