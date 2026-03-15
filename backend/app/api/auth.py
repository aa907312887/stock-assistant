import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.database import get_db
from app.models import User
from app.schemas.auth import Token, UserLogin, UserOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    logger.info("POST /api/auth/login 收到请求 username=%s", getattr(data, "username", ""))
    try:
        username = (data.username or "").strip()
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请输入用户名",
            )
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无此用户",
            )
        # 仅用户名登录，不校验密码
        token = create_access_token(sub=user.id)
        return Token(
            access_token=token,
            user=UserOut.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login error: %s", e)
        raise


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
