# Pokemon RP V2.5

桌面优先（Desktop-First）的宝可梦叙事 RPG 引擎。  
核心目标：在长线游玩中保持剧情一致性、世界观可追溯性和工程可维护性。

当前前端已升级到 **V2.5 JRPG 沉浸版**：
- 三栏游戏主界面（存档与任务 / 剧情舞台 / 队伍背包）
- Tailwind + shadcn 风格组件体系
- 文本流式渲染 + 动作卡交互
- 调试能力默认隐藏，仅开发模式开启

---

## 1. 版本定位

本仓库当前以 **V2 玩家端** 为主线：
- 玩家入口：`/adventure`
- 后端主协议：`/v2/game/*`
- 桌面壳：Electron（自动拉起后端 + 前端）

> V1 管理台相关页面与前端调用已清理，不再作为主流程维护。

---

## 2. 核心能力

- **长记忆叙事**：RAG + Timeline 双通道，避免“聊几轮就失忆”
- **结构化状态推进**：主线进度、队伍、仓库、背包、内核状态统一落库
- **SSE 回合流**：`ack -> primary -> delta -> done -> error`
- **动作卡玩法**：LLM 生成正式动作选项，点击即推进剧情
- **桌面可玩性优化**：自动滚动、状态反馈 toast、窗口化消息显示

---

## 3. 技术栈

### 后端
- Python 3.11+
- FastAPI / SQLAlchemy / Alembic
- SQLite（本地）/ PostgreSQL（可扩展）
- 讯飞 MaaS Provider（HTTP）

### 前端（V2.5）
- Next.js 15（App Router）
- React 19
- Tailwind CSS 3
- shadcn 风格组件（Radix primitives + 自定义 UI）
- TanStack Query

### 桌面端
- Electron

---

## 4. 前端 V2.5 改造说明

本次大迭代完成了以下前端重构：

1. **UI 栈切换**
- 从 AntD 管理台式样迁移到 Tailwind + shadcn 风格组件
- 建立统一主题 token（深海夜景 + 霓虹强调）

2. **信息架构重做**
- 左栏：存档管理 + 章节任务
- 中栏：剧情流 + 输入区 + 动作卡
- 右栏：队伍 / 仓库 / 背包常驻

3. **交互体验增强**
- 文本强调（粗体/斜体/下划线）与关键字高亮
- 回合结束后显示动作卡，避免中途抖动
- 状态变化（位置/金币/徽章）即时 toast 提示

4. **代码治理**
- 清理旧 V1 前端 API 封装与历史组件
- 统一 V2 类型与接口契约
- 删除乱码污染组件与无效依赖链

---

## 5. 本地启动（开发模式）

## 5.1 环境准备
- Python 3.11+
- Node.js 20+

## 5.2 配置环境变量
复制模板：

```powershell
copy .env.example .env
copy web\.env.local.example web\.env.local
```

至少需要配置（写入 `.env`）：
- `XF_APPID`
- `XF_API_KEY`
- `XF_API_SECRET`
- `XF_MODEL_ID`
- `LLM_PROVIDER=xfyun_http`

可选前端开关（写入 `web/.env.local`）：
- `NEXT_PUBLIC_RP_DEV_DEBUG_UI=false`（默认隐藏调试抽屉）

## 5.3 启动后端

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 5.4 启动前端

```powershell
cd web
cmd /c npm install
cmd /c npm run dev
```

访问：`http://127.0.0.1:3000/adventure`

## 5.5 启动桌面端

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_desktop.ps1
```

---

## 6. 质量检查

### 后端
```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

### 前端
```powershell
cd web
cmd /c npm run test
cmd /c npm run build
```

### 编码污染检查
```powershell
python scripts/check_mojibake.py
```

---

## 7. 关键 API（玩家端）

- `POST /v2/game/slots`：创建存档并生成开场
- `GET /v2/game/slots`：存档列表
- `GET /v2/game/slots/{slot_id}`：完整存档快照
- `POST /v2/game/slots/{slot_id}/turns?stream=true`：文本回合
- `POST /v2/game/slots/{slot_id}/actions/{action_id}?stream=true`：动作卡回合

完整协议见：[`PLAYER_API_V2.md`](./PLAYER_API_V2.md)

---

## 8. 常见问题

### Q1：桌面启动后白屏/超时
- 查看日志目录：`logs/`
- 重点检查：`backend.electron.stderr.log`、`frontend.electron.stderr.log`
- 确认端口：`8000`（后端）与 `3000`（前端）是否被占用

### Q2：回合很慢
- 优先检查模型服务时延（provider latency）
- 使用 `pace=fast` 可降低单轮上下文预算
- 确认模型 ID 与密钥匹配当前服务

### Q3：出现 `options_missing` / `primary_missing`
- 说明模型未按结构化约定返回
- 优先换更稳定模型或调低输出复杂度

---

## 9. 目录速览

```text
app/
  api/routers/game_v2.py
  services/v2/
  memory/
  providers/
  db/
web/
  src/app/adventure/page.tsx
  src/components/chat/ChatStreamView.tsx
  src/lib/api/endpoints.ts
  src/lib/schemas/types.ts
desktop/
  main.js
scripts/
  run_desktop.ps1
  check_mojibake.py
```

---

## 10. 安全说明

- 密钥只放 `.env`，不要提交到仓库
- 日志中禁止输出完整密钥或完整鉴权头
- 本地调试可开启 `AUTH_BYPASS_LOCAL`，生产环境必须关闭

---

## 11. 里程碑路线

- [x] V2 回合流与内核状态接入
- [x] V2.5 前端 JRPG 沉浸化重构
- [ ] 完整桌面发行包瘦身与签名
- [ ] 更细粒度战斗系统 UI 与编排
