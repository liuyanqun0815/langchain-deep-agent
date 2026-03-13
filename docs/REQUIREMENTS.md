# Agent 项目需求文档

## 1. 整体概述

本项目为在当前目录下新建的「Agent 应用」，包含：

- **前端**：基于 Vue 3 的单页应用（SPA）
- **后端**：基于 FastAPI 的 Python Web 服务
- **数据库**：本地文件形式的 SQLite，通过 ORM（如 SQLModel / SQLAlchemy）访问
- **智能体框架**：使用 langchain 的 deepagents 实现具备任务规划、文件系统上下文管理、子代理生成和长期记忆的 Agent，并支持动态集成 skills

系统目标：提供可视化的 Agent 管理与聊天界面，支持模型管理、技能管理、对话管理与历史会话查看。

---

## 2. 功能需求

### 2.1 模型展示与配置

- **模型列表展示**
  - 在页面展示当前可用的大模型列表（如 gpt-4.1、gpt-4.1-mini、local-llm 等）
  - 每条记录包含：模型名称（必填）、模型提供方/类型、模型描述（可选）、当前是否启用状态

- **模型配置**
  - 用户可在页面配置：默认对话模型、规划模型、工具调用/子 Agent 模型、最大 token 数、温度等
  - 配置修改后需持久化到本地（SQLite 或配置文件），并在后端生效（至少在新会话时生效）

- **模型健康检查与状态**
  - 前端可触发「测试模型」按钮，后端调用模型输出一条简单回复以验证配置可用
  - 前端展示测试结果（成功/失败及错误信息）

### 2.2 Skills 展示与管理

- **Skill 列表展示**
  - 展示当前系统中可用的 skills 列表（来源于代码内预注册 + 动态加载）
  - 每个 skill 包含：标识 ID、名称、描述、输入/输出简介（可选）、是否启用

- **Skill 添加**
  - 前端提供「添加 Skill」对话框，支持基础信息录入（名称、描述）、选择 skill 类型、录入或上传 skill 实现（第一版可简化为配置驱动，由后端生成固定模板）
  - 后端接收后：将 skill 元数据存入 SQLite，在内存中注册到 deepagents 的工具/skills 系统中（支持热加载），返回更新后的 skill 列表

- **Skill 启用/禁用**
  - 前端支持勾选/开关某个 skill 是否启用
  - 后端支持更新单个 skill 的启用状态，并动态刷新 Agent 的可用工具列表

### 2.3 聊天输入框与对话流程

- **聊天输入**
  - 页面下方提供聊天输入框：支持多行输入（Shift+Enter 换行，Enter 发送）、支持选择使用的目标 Agent 配置（第一版可选用「默认 Agent」）
  - 支持附加：选择当前会话（新会话/既有会话）、可选「任务描述模式」/「普通对话模式」

- **消息发送与响应**
  - 前端通过 REST API（或 WebSocket，第一版以 REST 为主）将用户输入发送到后端，请求包含：session_id、user_message、当前选中的模型/skill 配置
  - 后端调用 deepagents：使用长期记忆 + 文件系统上下文管理构建上下文，按需调用子 Agent 与 skills，返回模型回复

- **流式响应**
  - 第一版优先实现非流式（一次性完整回复）；若时间允许可支持 FastAPI StreamingResponse 的 SSE 或 chunk 流式输出

### 2.4 历史会话展示与管理

- **会话列表**
  - 左侧展示历史会话列表：会话 ID、会话标题（如首条用户消息前若干字）、创建时间、最近更新时间
  - 支持按时间排序、简单搜索（按标题关键字过滤）

- **会话详情**
  - 选中会话后，在主聊天区域展示该会话的全部消息历史：按时间顺序显示用户消息与 Agent 回复
  - 每条消息展示：发送方、时间戳、消息内容、可选的本轮模型/skill 信息

- **会话创建与切换**
  - 提供「新建会话」按钮：创建新 session_id 并入库，自动切换聊天区域到新会话
  - 切换会话时加载相应会话的历史消息

- **会话持久化**
  - 使用 SQLite 持久化：会话表（Session）、消息表（Message）、与会话相关的配置快照

---

## 3. Agent 功能与架构需求

### 3.1 基于 langchain deepagents 的 Agent 体系

- **任务规划（Task Planning）**
  - Agent 使用 deepagents 的 Planner 能力，将复杂用户请求拆分为多个子任务/子 Agent 调用，规划结果可在系统内部使用，前端第一版可只展示最终回复

- **文件系统上下文管理**
  - 配置用于上下文管理的「文件系统」，存储会话相关临时文件、用户上传内容等，Agent 可从中读写信息作为长期记忆的补充

- **子代理生成**
  - Agent 可在运行时根据任务类型生成子 Agent，子 Agent 可有不同模型或技能集（如代码分析 Agent、文档总结 Agent 等）

- **长期记忆**
  - 使用 deepagents 或 langchain 的记忆模块，将重要对话片段、用户偏好等存入向量库或本地存储（第一版可简化为 SQLite + 文本 embedding），在新问题中检索相关记忆作为上下文

### 3.2 动态集成 Skills

- **Skill 抽象设计**
  - 后端定义统一的 skill 抽象接口（如 BaseSkill）：统一的 name、description、invoke/__call__ 方法签名，对接 langchain/deepagents 的 Tool 或 StructuredTool 形式

- **Skill 动态加载/更新**
  - 初始化时从数据库读取所有启用状态的 skills 并注册到 Agent 工具列表
  - 添加新 skill 或修改启用状态时，动态更新内存中 Agent 的可用工具集，后续对话中可立即使用（至少在新会话中生效）

- **Skill 元数据存储**
  - SQLite 中为 skills 定义表：id、name、description、type、config（JSON）、enabled、created_at、updated_at
  - config 存储 skill 特定参数（如请求 URL、API key 等，需注意敏感信息存储方案）

---

## 4. 后端接口设计（初版）

### 4.1 模型与配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/models | 获取可用模型列表 |
| GET | /api/agent/config | 获取当前 Agent 配置 |
| PUT | /api/agent/config | 更新 Agent 配置 |
| POST | /api/models/test | 测试当前模型连通性 |

### 4.2 Skill 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/skills | 获取 Skill 列表 |
| POST | /api/skills | 新增 Skill |
| PATCH | /api/skills/{skill_id}/toggle | 更新 Skill 启用状态 |
| PUT | /api/skills/{skill_id} | 更新 Skill 配置（可选） |

### 4.3 会话与聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/sessions | 创建新会话 |
| GET | /api/sessions | 获取会话列表 |
| GET | /api/sessions/{session_id} | 获取单个会话详情（含消息） |
| POST | /api/sessions/{session_id}/messages | 发送消息给 Agent |

---

## 5. 数据库设计（SQLite）

### 5.1 表结构

- **sessions**
  - id（主键）、title、created_at、updated_at、config（JSON）

- **messages**
  - id（主键）、session_id（外键）、role（user/assistant/system）、content、metadata（JSON）、created_at

- **skills**
  - id（主键）、name、description、type、config（JSON）、enabled、created_at、updated_at

- **（可选）long_term_memory**
  - 后续用于存储 embedding、向量 ID 等，与向量库集成

---

## 6. 前端界面与交互需求

### 6.1 技术栈

- Vue 3（Composition API）、TypeScript（推荐）
- UI 组件库：Element Plus / Naive UI / Ant Design Vue 之一
- 使用 axios 或 fetch 调用后端 API

### 6.2 页面布局

- 顶部：应用标题与简单导航（模型配置、技能管理、聊天）
- 左侧：会话列表
- 中间：聊天区域（消息气泡、历史记录）
- 右侧或弹窗：模型配置与技能管理入口

### 6.3 必备组件

- ModelConfigPanel：模型列表及配置面板
- SkillListPanel：技能列表与添加技能表单
- ChatWindow：对话展示区域
- ChatInput：聊天输入框
- SessionList：会话列表

---

## 7. 非功能需求

- **代码规范**
  - 后端 Python：遵循 PEP8，使用 black（max_line_length=120），禁止 `from module import *`，变量命名 snake_case
  - 前端：组件命名清晰、单一职责，API 调用封装到独立模块

- **可维护性**
  - 后端按领域划分模块（routers、agent、db 等），明确 API 层、Agent 封装层、数据访问层

- **本地开发**
  - 提供 requirements.txt 或 pyproject.toml、前端 package.json、README 说明启动方式
