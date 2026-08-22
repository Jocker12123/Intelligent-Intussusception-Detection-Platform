import os

# 尝试加载同目录下的 .env 文件（若安装了 python-dotenv）。
# 没有 .env 或未安装 dotenv 时静默跳过，不影响现有运行。
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(BASE_DIR), "uploads"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# JWT 密钥：生产环境必须通过环境变量注入，避免使用内置默认值。
# 若开发环境未设置，则回退到开发占位值并在启动时告警（见 main.py）。
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

# 允许跨域的前端源。生产环境必须显式配置（禁止用 * 且允许凭证的组合）。
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# 医院所在时区（用于把数据库中的 naive UTC 时间换算成真实的"今天"边界）
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "Asia/Shanghai")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/bmp", "application/dicom"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024
