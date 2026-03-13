"""长期记忆：第一版使用 deepagents 内置的 /memories/ StoreBackend，此处仅预留扩展。"""

# 当前长期记忆由 create_deep_agent(store=..., backend=CompositeBackend(routes={"/memories/": StoreBackend}))
# 在 Agent 内部通过文件系统工具读写 /memories/ 路径实现，无需本模块额外逻辑。
# 后续可在此增加：从 DB 或向量库检索记忆并注入上下文的接口。
