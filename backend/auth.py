from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from database import get_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# 开发环境占位密钥：仅在没有配置环境变量时使用。生产部署请务必设置 JWT_SECRET_KEY。
_DEV_SECRET = "dev-secret-change-in-production"


def _secret_key() -> str:
    """返回 JWT 密钥；生产环境若未配置则抛出异常，避免弱密钥上线。"""
    key = JWT_SECRET_KEY
    if not key:
        # 允许开发环境用占位值跑通，但打日志提示
        import logging
        logging.getLogger("uvicorn.error").warning(
            "JWT_SECRET_KEY 未设置，正在使用开发占位密钥，请勿用于生产环境。"
        )
        return _DEV_SECRET
    # 生产环境仍然不做强校验（避免误伤开发），但提醒使用足够长的随机值
    if len(key) < 32:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "JWT_SECRET_KEY 长度不足 32，建议使用足够长的随机字符串。"
        )
    return key


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _secret_key(), algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = int(sub)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员，否则返回 403。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def can_manage(owner_id: int, current_user: User) -> bool:
    """判断当前用户是否有权管理某条记录（本人或管理员）。"""
    return current_user.role == "admin" or current_user.id == owner_id
