# Agent 项目技术概要设计文档

> 基于 [REQUIREMENTS.md](./REQUIREMENTS.md) 需求文档的技术概要设计。

---

## 1. 系统架构

### 1.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户浏览器 (Vue 3 SPA)                          │
├──────────────┬──────────────────────────────┬────────────────────────────┤
│ SessionList  │       ChatWindow             │ ModelConfig / SkillPanel   │
│ (会话列表)   │  (消息展示 + ChatInput)       │ (模型与技能管理)            │
└──────┬───────┴──────────────┬───────────────┴──────────────┬─────────────┘
       │                      │ HTTP/REST                    │
       ▼                      ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     FastAPI 后端 (Python)                                │
├─────────────┬─────────────┬─────────────┬────────────────────────────────┤
│ /api/       │ /api/       │ /api/       │ Agent 服务层                    │
│ sessions    │ skills      │ models      │ (deepagents 封装)               │
│ messages    │             │ agent/config│ - Planner / 子代理 / 记忆        │
└──────┬──────┴──────┬──────┴──────┬──────┴────────────┬───────────────────┘
       │             │             │                   │
       ▼             ▼             ▼                   ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────────────┐
│ SQLite       │ │ Skills 注册表 │ │ 文件系统 (上下文/临时文件)             │
│ sessions     │ │ (内存 + DB)   │ │ 长期记忆 (向量/文本)                   │
│ messages     │ │              │ │                                        │
│ skills       │ │              │ │                                        │
└──────────────┘ └──────────────┘ └──────────────────────────────────────┘
```

### 1.2 职责划分

| 层次 | 职责 |
|------|------|
| **前端** | 展示模型/技能/会话与消息，收集用户输入，调用后端 API，不直接访问数据库 |
| **API 层** | 路由、请求校验、调用服务层，返回 JSON |
| **服务层** | 业务逻辑：会话与消息 CRUD、技能 CRUD、Agent 调用与配置 |
| **Agent 层** | 封装 deepagents：规划、子代理、文件系统上下文、长期记忆、工具/skills 调用 |
| **数据层** | SQLite 的增删改查（ORM），技能与配置的持久化 |

### 1.3 核心数据流

- **发送消息**：前端 `POST /api/sessions/{id}/messages` → 服务层加载会话历史与配置 → Agent 层构建上下文、执行规划与工具调用 → 写入 messages 表 → 返回 assistant 消息。
- **技能变更**：前端 `POST /api/skills` 或 `PATCH /api/skills/{id}/toggle` → 服务层写 DB 并调用「技能注册器」→ Agent 工具列表在内存中更新，新会话或下次调用时生效。

---

## 2. 技术选型

### 2.1 前端

| 项目 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 | Composition API + `<script setup>` |
| 语言 | TypeScript | 类型安全，与后端接口对齐 |
| 构建 | Vite | 快速冷启与 HMR |
| UI 库 | Element Plus / Naive UI 二选一 | 表格、表单、对话框、布局 |
| HTTP | axios | 封装 baseURL、拦截器、错误提示 |
| 状态 | Pinia（可选） | 会话列表、当前会话、全局配置等可集中管理 |

### 2.2 后端

| 项目 | 选型 | 说明 |
|------|------|------|
| 框架 | FastAPI | 异步支持、自动 OpenAPI、类型校验 |
| ORM | SQLModel | 与 Pydantic 一致，模型即 schema，便于与 FastAPI 集成 |
| 数据库 | SQLite | 单文件 `agent_app.db`，无需独立服务 |
| Agent | langchain + deepagents | 任务规划、子代理、文件系统、长期记忆 |
| 配置 | pydantic-settings | 从环境变量/`.env` 读取 API Key、模型名等 |

### 2.3 开发与质量

- Python：black（line-length=120）、ruff 或 flake8、类型注解
- 前端：ESLint、Prettier，与后端约定 API 路径与请求/响应体

---

## 3. 后端模块与目录结构

### 3.1 推荐目录结构

```
backend/
├── main.py                 # FastAPI 应用入口，挂载路由、初始化 DB/Agent
├── config.py               # pydantic-settings 配置（数据库 URL、模型默认值等）
├── requirements.txt        # 或 pyproject.toml
├── app/
│   ├── __init__.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py      # 获取 Session / engine
│   │   └── models.py       # SQLModel 模型：Session, Message, Skill
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── sessions.py     # 会话与消息 API
│   │   ├── skills.py       # 技能 CRUD 与 toggle
│   │   ├── models.py       # 模型列表、测试
│   │   └── agent_config.py # Agent 配置读写
│   ├── services/
│   │   ├── __init__.py
│   │   ├── session_service.py   # 会话与消息的创建、查询
│   │   ├── skill_service.py     # 技能 CRUD、同步到 Agent
│   │   └── agent_service.py     # 调用 Agent、构建上下文、写回消息
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── factory.py      # 创建 deepagents Agent（含 planner、记忆、工具）
│   │   ├── context.py      # 文件系统上下文管理
│   │   ├── memory.py       # 长期记忆封装（检索、写入）
│   │   └── skills/
│   │       ├── __init__.py
│   │       ├── base.py     # BaseSkill / 与 LangChain Tool 的适配
│   │       └── registry.py # 从 DB 加载 skills 并注册到 Agent
│   └── schemas/
│       ├── __init__.py
│       ├── session.py      # SessionCreate, MessageOut 等
│       ├── skill.py        # SkillCreate, SkillOut
│       └── agent_config.py # AgentConfigUpdate
```

### 3.2 模块职责简述

- **routers/**：仅做参数解析、调用 service、返回响应，不直接操作 ORM 或 Agent。
- **services/**：会话/消息/技能的 CRUD；调用 `agent_service` 发送用户消息并写回 assistant 消息。
- **agent/**：deepagents 的组装、上下文与记忆的注入、skills 的动态注册；对外提供「单次对话」接口（输入：session_id + user_message，输出：assistant 内容）。

---

## 4. Agent 集成设计

### 4.1 总体流程

1. **启动时**：从 SQLite 加载启用中的 skills → 转为 LangChain Tool 列表 → 创建 deepagents Agent（Planner + 子代理能力 + 文件系统 + 长期记忆）并注入工具。
2. **收到用户消息时**：根据 session_id 加载历史消息与长期记忆片段 → 拼成当前轮次的上下文 → 调用 Agent → 将 assistant 回复写入 messages 表，必要时更新长期记忆与文件系统。

### 4.2 任务规划与子代理

- 使用 deepagents 提供的 **Planner**：将复杂 query 拆成子任务，决定是否调用子 Agent 或工具。
- **子代理**：按任务类型（如代码分析、文档总结）实例化不同配置的 Agent（可不同模型或不同工具子集），由主 Agent 在规划阶段决定调用关系。
- 第一版可在同一进程内用「子 Agent 函数」封装，不强制多进程。

### 4.3 文件系统上下文管理

- 为每个会话维护一个逻辑「工作目录」或命名空间（如 `context/session_{session_id}/`）。
- Agent 可读写的临时文件、上传文件（后续扩展）均落在此目录，便于做上下文窗口管理（如按文件摘要注入）。
- 实现层可与 langchain 的 FileSystemTool 或自研轻量封装对接。

### 4.4 长期记忆

- **存储**：第一版可采用「SQLite + 文本」或「SQLite + 简单 embedding 向量」；后续可切换为独立向量库。
- **写入时机**：在 assistant 回复后，由服务层或 Agent 层筛选「需要记忆」的片段（如用户偏好、关键结论），写入 memory 表或向量库。
- **读取时机**：在构造当前轮次上下文时，根据当前 user_message 检索 Top-K 条相关记忆，拼入 system 或 history。

### 4.5 Skills 动态集成

- **BaseSkill**：统一接口（name、description、invoke），适配为 LangChain `StructuredTool` 或 `Tool`。
- **SkillRegistry**：维护「当前已启用 skill_id → Tool 实例」的映射；提供 `reload_from_db()`，在新增/启用/禁用 skill 后由 service 调用，重建工具列表并更新 Agent 的 tools 属性（或重建 Agent 实例）。
- **配置驱动 Skill**：第一版可从 DB 的 `skills.config` 生成固定模板工具（如 HTTP 请求、简单计算），避免执行任意用户代码带来的安全风险。

---

## 5. 数据模型与存储

### 5.1 ORM 模型（SQLModel）

- **Session**：id (UUID 或自增)、title、created_at、updated_at、config (JSON)。
- **Message**：id、session_id (FK)、role (Enum: user/assistant/system)、content (Text)、metadata (JSON)、created_at。
- **Skill**：id、name、description、type、config (JSON)、enabled (Boolean)、created_at、updated_at。

### 5.2 索引与约束

- `messages.session_id` 建索引，便于按会话分页拉取。
- `skills.enabled` 可建索引便于筛选启用列表。
- 外键：Message.session_id → Session.id，删除会话时级联或限制删除消息（按产品需求选择）。

### 5.3 配置与敏感信息

- 模型 API Key、base URL 等放在环境变量或 `.env`，由 pydantic-settings 读取，不落库。
- `skills.config` 中若含密钥，考虑加密存储或仅存「配置键名」，实际密钥由环境变量注入。

---

## 6. API 设计概要

### 6.1 统一约定

- 基础路径：`/api`。
- 成功：HTTP 200/201，body 为资源或列表；错误：4xx/5xx + JSON `{ "detail": "..." }`。
- 列表接口支持 `limit`、`offset` 或 `page`/`page_size`（与需求文档一致即可）。

### 6.2 与需求文档的对应关系

| 需求章节 | 实现要点 |
|----------|----------|
| 4.1 模型与配置 | `GET/PUT /api/agent/config` 读写当前 Agent 使用的模型与参数；`GET /api/models` 返回可选模型列表；`POST /api/models/test` 调用一次 LLM 做连通性测试 |
| 4.2 Skill 管理 | `GET /api/skills` 查 DB；`POST /api/skills` 写 DB 并触发 SkillRegistry.reload；`PATCH /api/skills/{id}/toggle` 更新 enabled 并 reload |
| 4.3 会话与聊天 | `POST /api/sessions` 创建 Session；`GET /api/sessions` 分页列表；`GET /api/sessions/{id}` 返回会话 + 消息列表；`POST /api/sessions/{id}/messages` 入参 user_message，内部调 Agent 后追加两条 Message（user + assistant）并返回 assistant 内容 |

### 6.3 请求/响应示例（概要）

- **POST /api/sessions/{session_id}/messages**  
  - Request: `{ "user_message": "..." }`  
  - Response: `{ "role": "assistant", "content": "...", "message_id": "...", "created_at": "..." }`

- **GET /api/sessions**  
  - Response: `{ "items": [ { "id", "title", "created_at", "updated_at" } ], "total": n }`

---

## 7. 前端设计概要

### 7.1 路由与页面

- `/` 或 `/chat`：主界面（左侧会话列表 + 中间聊天 + 右侧或弹窗的配置/技能）。
- `/models`、`/skills`：可与主界面合并为 Tab 或抽屉，按需求文档「模型配置、技能管理、聊天」组织即可。

### 7.2 状态与 API 调用

- 当前会话 id、当前会话消息列表、会话列表、技能列表、Agent 配置等可由 Pinia 或 composable 管理。
- 所有请求通过封装的 `api` 模块（axios 实例）访问 `/api/*`，便于统一错误提示与鉴权扩展。

### 7.3 组件与需求对应

- **SessionList**：调用 `GET /api/sessions`，点击项时切会话并拉取 `GET /api/sessions/{id}`。
- **ChatWindow**：展示当前会话的 messages，底部为 **ChatInput**；发送时 `POST /api/sessions/{id}/messages`，将返回的 assistant 消息追加到列表。
- **ModelConfigPanel**：`GET /api/agent/config`、`GET /api/models`，保存时 `PUT /api/agent/config`，测试时 `POST /api/models/test`。
- **SkillListPanel**：`GET /api/skills`，添加 `POST /api/skills`，切换启用 `PATCH /api/skills/{id}/toggle`。

---

## 8. 部署与运行

### 8.1 本地开发

- **后端**：`uvicorn main:app --reload --reload-exclude 'skills/**'`，默认 SQLite 文件放在项目目录或 `data/` 下；`--reload-exclude` 排除 `skills/` 目录，避免从本地路径添加技能时触发不必要的重启。
- **前端**：`npm run dev`，通过 Vite 代理或直接配置 `VITE_API_BASE_URL` 指向后端（如 `http://localhost:8000`）。
- **首次启动**：执行 SQLModel 的 `create_all()` 或 Alembic 初始化，并可选执行 skills 种子数据。

### 8.2 环境变量示例

- `DATABASE_URL=sqlite:///./agent_app.db`
- `OPENAI_API_KEY=`（或对应模型供应商的 key）
- `DEFAULT_MODEL=`、`PLANNER_MODEL=`（可选，否则用配置表或代码默认值）

---

## 9. 风险与扩展

- **deepagents 版本与 API**：以当前 langchain/deepagents 文档为准，若 API 与本文不一致，以「任务规划 + 子代理 + 工具 + 记忆」的职责不变为前提做适配。
- **流式输出**：若后续支持 SSE，需在 `agent_service` 中改为 yield 内容，并对应 `StreamingResponse` 与前端 EventSource/fetch 流解析。
- **多用户与鉴权**：第一版可为单用户；后续可在 API 层加鉴权，并在 Session/Message 上增加 `user_id` 等字段做隔离。

---

本文档与 [REQUIREMENTS.md](./REQUIREMENTS.md) 共同作为实现与评审依据，具体实现时以实际代码与依赖版本为准。
