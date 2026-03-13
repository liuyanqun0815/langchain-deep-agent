# Agent 技能说明

本项目支持**两套**与能力相关的机制，对应 LangChain DeepAgent 的两种扩展方式：

1. **Tools（工具）**：可调用的函数，来自本项目的 `skill.yaml` + Python/HTTP 配置或内置类型，对应 `create_deep_agent(tools=[...])`。
2. **Skills（官方技能）**：按 [Agent Skills 规范](https://agentskills.io/specification) 的 **SKILL.md** 目录，对应 `create_deep_agent(skills=["/skills/"])`，采用渐进式披露（按需读取说明与资源）。  
   官方文档：[DeepAgent Skills](https://docs.langchain.com/oss/python/deepagents/skills)。

技能/工具根目录默认在 **`backend/skills/`**，可通过环境变量 `SKILLS_ROOT` 覆盖。

---

## 一、官方 Skills（SKILL.md）

- 每个技能是一个**子目录**，目录内必须有 **SKILL.md**（不是 skill.yaml）。
- SKILL.md 为 Markdown，**开头用 YAML frontmatter** 写 `name`、`description` 等，正文写使用说明与步骤。
- Agent 启动时只会读 frontmatter；只有在判定任务匹配时才会读取完整 SKILL.md 内容（渐进式披露）。
- 本项目在创建 Agent 时：
  - 将 `skills/` 映射到后端路径 `/skills/`（FilesystemBackend），
  - 若存在至少一个包含 SKILL.md 的子目录，则调用 `create_deep_agent(skills=["/skills/"])`，由 DeepAgent 按官方逻辑加载。

### SKILL.md 示例

```markdown
---
name: my-skill
description: 在用户询问 X 时使用本技能，用于……
---

# my-skill

## 概述

本技能用于……

## 使用步骤

1. 第一步……
2. 第二步……
```

更多字段与规范见 [Agent Skills Specification](https://agentskills.io/specification)。注意：description 超过 1024 字符会被截断；单文件需在 10 MB 以内。

### 示例技能目录

在 `backend/skills/` 下新建子目录并放入 SKILL.md 即可，例如：

```text
backend/skills/
├── langgraph-docs   # 官方示例风格
│   └── SKILL.md
└── my-skill
    └── SKILL.md
```

重启服务或调用 `rebuild_agent` 后，Agent 会加载这些技能。

---

## 二、Tools（skill.yaml + 可调用工具）

- 每个工具对应 `backend/skills/` 下的一个**子目录**，目录内需有 **skill.yaml**（或 skill.yml / skill.json）作为清单。
- 这些会通过本项目的注册逻辑转为 **tools** 传给 `create_deep_agent(tools=[...])`，与上述 SKILL.md 技能**同时生效**（SKILL.md 提供说明与流程，tools 提供可执行函数）。

### skill.yaml 规范

```yaml
name: my_skill
description: "工具描述，供模型理解用途"
type: python    # python | http
entry_point: skill:tool   # 仅 type=python：模块名:函数名
config: {}      # 可选，type=http 时可填 url 等
```

- **type: python**：从该目录下的 Python 模块加载可调用对象；`entry_point` 格式为 `模块名:函数名`，或使用约定（如 `skill.py` 的 `tool` / `skill`）。
- **type: http**：使用内置 HTTP 工具，`config` 可含 `url`、`method` 等。

### 启动时加载

1. 创建 `backend/skills/` 目录（若不存在）。
2. 扫描子目录：含 **skill.yaml** 的会同步到 DB（Tools）；含 **SKILL.md** 的会在构建 Agent 时作为官方 skills 路径使用。
3. 从 DB 加载已启用的 Tools 并注册到 Agent。

### 动态添加

- **本地 Tools**：在 `skills/` 下新建子目录，放入 skill.yaml（及 Python 等），然后 `POST /api/skills/from-local`，body: `{"source_path": "子目录名"}`，或重启由同步逻辑发现。
- **GitHub Tools**：仓库中需存在 `skills/` 目录，且 `skills/` 下每个子目录代表一个技能（例如 `repo/skills/a`、`repo/skills/b`）。调用 `POST /api/skills/from-github`，body: `{"repo_url": "https://github.com/owner/repo"}` 或 `{"repo_url": "owner/repo"}`。系统会将 `repo/skills/*` **复制到当前项目根目录 `skills/` 下**，并为每个技能创建一条独立 Skill 记录（可单独开关）。返回值为 **技能列表**。
- **官方 Skills**：在 `skills/` 下任意子目录中增加或修改 **SKILL.md**，重启或重建 Agent 后即可被 DeepAgent 按路径 `/skills/` 发现。

---

## 三、对比小结

| 项目       | Tools（本项目）     | Skills（官方 SKILL.md）      |
|------------|---------------------|-----------------------------|
| 清单文件   | skill.yaml          | SKILL.md                    |
| 用途       | 注册可调用工具      | 提供说明与步骤，按需读取    |
| 加载方式   | DB + 注册表 → tools | 目录路径 → create_deep_agent(skills=[...]) |
| 规范/文档  | 本项目约定          | [Agent Skills 规范](https://agentskills.io/specification)、[DeepAgent Skills](https://docs.langchain.com/oss/python/deepagents/skills) |

同一 `backend/skills/` 目录下可以既有 **SKILL.md**（官方技能），又有 **skill.yaml** + Python（Tools），两者会同时被使用。
