# Pokemon RP Engine

企业级宝可梦角色扮演引擎（Pokemon RP Engine）。
本项目不是“普通聊天壳”，而是一个可上线、可维护、可观测、可扩展的后端系统：
以 `RAG 语义记忆 + Timeline 时间线` 实现长期记忆，以 `Canon Data Layer` 保证宝可梦世界观与设定一致性，以 Provider 抽象支持讯飞星辰 GLM-5（`xopglm5`）与后续多模型扩展。

## 为什么这个项目不一样

- 不依赖模型上下文长度“硬塞历史”，而是通过长期记忆系统稳定回忆早期信息
- LLM 被降级为“叙事引擎”，事实以 Canon 数据层为唯一权威
- Timeline 中 `confirmed` 事实不可覆盖，冲突通过 `conflict + open_thread` 机制解决
- 内建审计、链路追踪、指标、限流、鉴权、RBAC、CI，满足工程化交付标准

## 核心能力

- 记忆系统（固定流水线）
  - `QueryBuilder -> MemoryRetriever -> Compression -> PromptAssembler -> LLM -> CanonFactChecker -> MemoryWriter`
- 双通道长期记忆
  - `CANON_FACTS`：来自 Timeline confirmed，硬事实
  - `RELEVANT_RECALLS`：来自向量召回，软回忆
  - `OPEN_THREADS`：悬念/任务/冲突线索
- Canon 事实校验
  - 模型输出中的 `facts_used[]` 与 Canon DB 对照校验
  - 不一致时自动触发修复重写，仍失败则返回“资料不足/版本不一致”
- 模型接入
  - `mock`（默认，便于本地开发和测试）
  - `xfyun_http`（讯飞 HTTP 推理）
  - `xfyun_ws`（讯飞 WS 流式，含 HMAC-SHA256 鉴权 URL 生成）
- 工程能力
  - JWT 鉴权 + RBAC（`admin/operator/viewer/user`）
  - Redis 限流（用户维度）
  - JSON 结构化日志 + `trace_id`
  - Prometheus 指标 + `healthz/readyz`
  - Docker Compose 一键部署 + K8s 基础清单 + GitHub Actions

## 技术栈

- Python 3.11
- FastAPI + Uvicorn
- PostgreSQL 15 + pgvector
- Redis
- SQLAlchemy 2.x + Alembic
- pytest / ruff / black / mypy

## 3 分钟启动（推荐）

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
```

请至少修改：

- `JWT_SECRET`：生产必须使用高强度长密钥（建议 >= 32 字符）
- `LLM_PROVIDER`：本地建议先用 `mock`
- `CORS_ALLOWED_ORIGINS`：前端联调建议包含 `http://localhost:3000`

### 2. 一键启动

```powershell
docker compose up --build
```

启动成功后可访问：

- OpenAPI 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/healthz`
- 就绪检查：`http://localhost:8000/readyz`
- 指标：`http://localhost:8000/metrics`

### 3. 可选：初始化 Canon 种子数据

```powershell
python scripts/dev_seed.py
```

## 运行模式说明

### 模式 A：本地开发（无外部密钥）

```env
LLM_PROVIDER=mock
```

特点：

- 不访问外部模型服务
- 测试稳定、可复现
- 适合作为 CI 和功能开发默认模式

### 模式 B：讯飞 HTTP（生产主路径）

```env
LLM_PROVIDER=xfyun_http
XF_APPID=...
XF_API_KEY=...
XF_API_SECRET=...
XF_MODEL_ID=xopglm5
XF_BASE_URL_HTTP=https://maas-api.cn-huabei-1.xf-yun.com/v1
XF_AUTH_MODE=bearer
```

补充：当 `XF_BASE_URL_HTTP` 使用 `.../v2` 时，后端会自动按 `APIKey:APISecret` 组装 Bearer token。

如控制台要求三元头鉴权，可切换：

```env
XF_AUTH_MODE=header_triple
```

### 模式 C：讯飞 WS（实时流式场景）

```env
LLM_PROVIDER=xfyun_ws
XF_BASE_URL_WS=wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat
```

> 注意：严禁在日志、文档、代码中输出真实密钥或完整 authorization 串。

## 本地开发流程

```powershell
python -m pip install -e .[dev]
alembic upgrade head
python scripts/dev_seed.py
uvicorn app.main:app --reload
```

## 正式管理台前端（Next.js 15）

仓库已包含独立管理台应用目录 `web/`，用于会话测试、SSE 调试、记忆注入检查、冲突确认、指标看板与 Canon 查询。

### 前端启动

```powershell
cd web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

默认前端地址：`http://localhost:3000`  
默认后端地址：`http://localhost:8000`（由 `NEXT_PUBLIC_API_BASE_URL` 控制）

### EXE 一键启动（Windows）

已提供一键启动器源码与打包脚本：

- `scripts/one_click_launch.py`
- `scripts/build_one_click_exe.ps1`

如果你已打包成功，可直接双击：

- `dist/PokemonRP-Start.exe`

启动器会自动：

- 检查 Python / npm
- 生成 `web/.env.local`（若不存在）
- 初始化本地 SQLite 表
- 拉起后端（8000）和前端（3000）
- 默认不打开浏览器（独立运行）

可配置默认是否自动打开浏览器：

- 不打开（默认）：`RP_OPEN_BROWSER=0`
- 打开：`RP_OPEN_BROWSER=1`

命令行可临时覆盖：

- 强制打开：`PokemonRP-Start.exe --open-browser`
- 强制不打开：`PokemonRP-Start.exe --no-browser`

### 桌面客户端（完全不用系统浏览器）

新增内嵌窗口桌面端启动器（基于 `Electron`）：

- PowerShell 一键运行：`scripts/run_desktop.ps1`
- 可打包 EXE：`scripts/build_desktop_exe.ps1` -> `dist/PokemonRP-Desktop-win32-x64/PokemonRP-Desktop.exe`

启动命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_desktop.ps1
```

说明：

- 桌面端主程序位于 `desktop/main.js`
- 桌面端会托管后端 `127.0.0.1:8000` 和前端 `127.0.0.1:3000`
- UI 在内嵌窗口打开，不会调用系统默认浏览器
- 关闭桌面窗口后，会自动结束托管的前后端子进程

## Debug 日志（推荐）

- 默认日志文件：`logs/rp-engine.log`
- 请求日志字段：`trace_id / method / path / status_code / duration_ms / slow`
- 每个响应头会带：
  - `X-Trace-Id`
  - `X-Process-Time-Ms`

快速查看最近日志（PowerShell）：

```powershell
Get-Content logs/rp-engine.log -Tail 200
```

管理接口（admin/operator）：

```bash
GET /v1/admin/logs/recent?lines=200
```

### 前端功能清单

- 登录鉴权（JWT，sessionStorage）
- 前端注册页（`/register`）
- 会话列表 / 新建 / 删除 / 导出
- 会话详情 + 流式对话（SSE）
- 记忆调试面板（`/memory/debug`）
- 冲突与 pending 事件确认（`/timeline/events` + `/memory/confirm`）
- Ops 指标卡片（`/v1/admin/metrics/summary`）
- Canon 数据检索（pokemon / moves / type-chart）

### 管理员权限初始化

默认管理员账号（启动自动创建）：

- 账号：`admin`
- 密码：`admin`

如果要提升已有账号角色，可用脚本：

```powershell
python scripts/promote_role.py --email admin@example.com --role admin
```

可选角色：`admin | operator | viewer | user`

## API 快速体验

### 1. 注册

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Password123!"}'
```

### 2. 登录

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Password123!"}'
```

### 3. 创建会话

```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Kanto Run","canon_gen":9,"canon_game":"sv"}'
```

### 4. 非流式消息

```bash
curl -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/messages \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"text":"我们去常磐森林","stream":false}'
```

### 5. 流式消息（SSE）

```bash
curl -N -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/messages \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"text":"继续剧情","stream":true}'
```

### 6. 记忆调试（admin/operator）

```bash
curl -X GET http://localhost:8000/v1/sessions/<SESSION_ID>/memory/debug \
  -H "Authorization: Bearer <TOKEN>"
```

### 7. 导出会话（GDPR-like）

```bash
curl -X GET "http://localhost:8000/v1/sessions/<SESSION_ID>/export?fmt=json" \
  -H "Authorization: Bearer <TOKEN>"
```

## 记忆与一致性策略（设计要点）

- Prompt 注入顺序固定：
  - `SYSTEM`
  - `CANON_FACTS`
  - `RELEVANT_RECALLS`
  - `OPEN_THREADS`
  - `SHORT_WINDOW`
- 冲突处理：
  - 新事实与 confirmed 冲突时，不覆盖旧事实
  - 追加 `canon_level=conflict`
  - 创建 `open_thread` 供后续剧情解释/确认
- 上下文预算控制：
  - recall/open_thread 按重要度裁剪，避免 token 爆炸

## 可观测与运维

- 日志：结构化 JSON，包含 `trace_id/session_id/turn_id`
- 指标：
  - `rp_requests_total`
  - `rp_provider_latency_seconds`
  - `rp_retrieval_vector_hits_total`
  - `rp_retrieval_timeline_hits_total`
  - `rp_turns_created_total`
  - `rp_conflicts_total`
- 健康探针：`/healthz`、`/readyz`

## 测试与质量门禁

```powershell
python -m ruff check app tests scripts
python -m black --check app tests scripts
python -m mypy app
python -m pytest -q
```

当前仓库默认测试覆盖：

- WS 鉴权 URL 生成
- 记忆压缩与裁剪
- 冲突检测逻辑
- 端到端对话链路（含 memory debug）

## 项目结构（核心）

```text
app/
  api/            # 路由与依赖注入
  canon/          # Canon 数据校验、拉取与校验脚本
  core/           # 配置、日志、限流、鉴权、trace、metrics
  db/             # 模型与迁移
  memory/         # 记忆流水线
  providers/      # mock / xfyun_http / xfyun_ws
  services/       # 业务编排层
  utils/          # 工具函数
scripts/          # 数据脚本、压测脚本
tests/            # 单测+集成测试
deploy/k8s/       # K8s 示例清单
templates/        # 世界观/角色卡/提示模板
web/              # Next.js 正式管理台
```

## 生产部署建议

- 本地：`docker-compose.yml`
- 集群：`deploy/k8s/api-deployment.yaml` + `deploy/k8s/ingress.yaml`
- CI：`.github/workflows/ci.yml`

上线前建议补齐：

- 独立 PostgreSQL/Redis 高可用方案
- OTel 全链路追踪
- 统一告警（请求错误率、provider 超时、限流命中）
- 密钥轮换流程自动化

## 常见问题

- `pgvector extension missing`
  - 使用 `pgvector/pgvector:pg15` 镜像
  - 执行 `alembic upgrade head`
- `429 Too Many Requests`
  - 调整 `.env`：`RATE_LIMIT_QPS` / `RATE_LIMIT_BURST`
- `迁移失败`
  - 检查 `DATABASE_URL`
  - 确认数据库服务已 ready
- `讯飞调用失败`
  - 先切回 `LLM_PROVIDER=mock` 定位业务逻辑
  - 再逐项核对 `XF_*` 配置与鉴权模式

## 合规与版权提示

本仓库仅提供结构化事实数据流程与拉取脚本，不内置官方图鉴原文/游戏素材。请在使用时遵守相关版权、商标及数据源条款。
