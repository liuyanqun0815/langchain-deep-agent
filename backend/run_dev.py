"""启动 uvicorn 并排除 skills 目录，避免添加技能时触发 reload。"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 监听 app 和当前目录（含 main.py, config.py），排除 skills（需 watchfiles）
        reload_dirs=["app", "."],
        reload_excludes=["**/skills/**", "skills", "skills/*"],
    )
