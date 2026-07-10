from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_access import has_unlimited_credits, is_admin
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import TokenResponse, UserLogin, UserOut, UserRegister, UserUpdate
from app.security import create_access_token, hash_password, verify_password
from app.services.credits import ensure_balance_row, get_balance

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(db: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        created_at=user.created_at,
        credits=get_balance(db, user.id),
        is_admin=is_admin(user),
        unlimited_credits=has_unlimited_credits(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta zaten kayıtlı",
        )

    settings = get_settings()
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        preferred_language=payload.preferred_language or "tr",
    )
    db.add(user)
    db.flush()

    ensure_balance_row(db, user, initial=settings.initial_credits)
    from app.models import CreditTransaction

    if settings.initial_credits > 0:
        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=settings.initial_credits,
                reason="Kayıt bonusu",
                reference_type="signup",
                reference_id=None,
            )
        )

    db.commit()
    token = create_access_token(user.id, extra={"email": user.email})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif",
        )
    token = create_access_token(user.id, extra={"email": user.email})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return _user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
    db.commit()
    db.refresh(user)
    return _user_out(db, user)
