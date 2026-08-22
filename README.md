# 儿童肠套叠超声影像AI辅助诊断平台

大学科研项目。平台提供超声影像上传和AI检测功能，辅助临床医生诊断儿童肠套叠。

## 技术栈

- **前端**: Vue 3 + Element Plus + Vite + Pinia + Axios
- **后端**: FastAPI + SQLAlchemy + SQLite + JWT
- **算法**: Python 函数接口，平台内置 Mock 实现，团队可替换为真实模型

## 快速开始

### 1. 启动后端
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

首次启动自动创建测试账号：
- 管理员: admin / admin123
- 医生: doctor / doctor123

API 文档: http://127.0.0.1:8000/docs

### 生产环境配置（安全必需）

平台默认使用「开发占位密钥」，仅用于本地跑通。部署到医院内网前请设置以下环境变量：

| 环境变量 | 说明 | 默认（本地开发） |
|---------|------|----------------|
| `JWT_SECRET_KEY` | JWT 签名密钥，**生产必须设置**且用长度≥32 的随机字符串 | 开发占位密钥（会告警） |
| `ALLOWED_ORIGINS` | 允许跨域的前端源，多个用逗号分隔，**不要用 `*`** | `http://localhost:5173,http://127.0.0.1:5173` |
| `LOCAL_TIMEZONE` | 医院所在时区（用于"今日"统计边界） | `Asia/Shanghai` |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///.../app.db` |
| `UPLOAD_DIR` | 影像存储目录 | 项目根目录下的 `uploads/` |

> 可用 `backend/.env.example` 作为模板，复制为 `.env` 并填上实际值（后端启动时会自动加载 `.env`）。

示例（Windows，临时设置）：
```powershell
$env:JWT_SECRET_KEY = "请换成一段至少32位的随机字符串"
$env:ALLOWED_ORIGINS = "http://your-frontend-host:port"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

权限说明：普通医生只能编辑/删除**自己录入**的患者与自己上传的影像；管理员可管理全部数据。仅管理员可修改系统设置。

### 审计日志

平台会记录每位医护人员的操作（登录、新增/编辑/删除患者、上传/删除影像、发起检测、修改设置），含时间、操作人、来源 IP、对象和详情。管理员登录后，左侧菜单可进入「审计日志」页查看与搜索、按日期范围筛选、导出 CSV；后端接口为 `GET /api/audit` 与 `GET /api/audit/export`（仅管理员可访问）。

### 检测机制说明

- 影像上传后默认走**异步检测**（提交任务 → 前端轮询进度 → 完成后跳转结果页），避免真实模型推理阻塞请求。
- 平台同时保留同步检测接口 `POST /api/images/{id}/detect` 与异步接口 `POST /api/detection/tasks/{image_id}` + `GET /api/detection/tasks/{task_id}`。
- 检测结果会记录**模型名/版本/推理耗时**，并支持**多分类概率**展示。

### 数据库迁移（Alembic）

平台已内置 Alembic 用于管理数据库结构变更。新增表/字段时：
```bash
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
```
> 项目启动仍会通过 `create_all` + 幂等补列保证旧库可用，Alembic 供团队在结构演进时使用。

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

### 3. 运行测试
```bash
# 后端
cd backend
pytest tests/ -v

# 前端（单元测试）
cd frontend
npm test
```

## 算法对接

算法团队需实现 `backend/algorithm/interface.py` 中定义的 `detect_intussusception` 函数。平台已经帮你处理了影像的接收、存储和结果落库，你只需要：读取 `image_path` → 推理 → 返回 `DetectionResult`。

> 对接提示：`severity`、`treatment_success_rate`、`treatment_advice` 都是可选字段，可以省略不填（平台会按分类给出默认建议），不会因为缺字段报错。只填必填项也能跑通。

```python
from pathlib import Path
from algorithm.interface import DetectionResult

def detect_intussusception(image_path: Path) -> DetectionResult:
    # 1. 加载你的模型
    # 2. 读取/预处理 image_path
    # 3. 推理
    # 4. 返回结果（可只填必填项）
    return DetectionResult(
        classification="肠套叠阳性",   # 必填: 肠套叠阳性 | 肠套叠阴性 | 图像质量不佳
        confidence=0.95,              # 必填: 0.0 ~ 1.0
        severity="中度",              # 可选: 轻度 | 中度 | 重度
        treatment_success_rate=0.86,  # 可选: 0.0 ~ 1.0
        treatment_advice="建议空气灌肠复位",  # 可选
    )
```

将实现文件放入 `backend/algorithm/` 目录即可，平台会自动调用。完整字段说明见 `backend/algorithm/interface.py` 顶部注释。

## 项目结构
```
├── backend/          # FastAPI 后端
│   ├── routers/      # API 路由
│   ├── services/     # 业务逻辑
│   ├── algorithm/    # 算法接口+Mock
│   └── tests/        # pytest 测试
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── views/    # 页面组件
│       ├── components/ # 通用组件
│       ├── api/      # API 调用封装
│       ├── router/   # 路由配置
│       └── stores/   # Pinia 状态
└── uploads/          # 影像存储
```
