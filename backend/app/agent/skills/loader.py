"""从磁盘或 GitHub 按需加载技能：解析 skill.yaml，执行 entry_point 或构建内置类型。"""

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from config import settings


def parse_skill_manifest(skill_dir: Path) -> dict[str, Any] | None:
    """解析技能目录下的 skill.yaml 或 skill.json，返回 manifest 字典。"""
    for name in ("skill.yaml", "skill.yml", "skill.json"):
        path = skill_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text) or {}
        if path.suffix == ".json":
            import json

            return json.loads(text)
    return None


def _load_python_entry_point(skill_dir: Path, entry_point: str) -> Callable[..., Any] | None:
    """从 entry_point（如 skill:tool）加载并返回可调用对象。"""
    import sys

    if ":" not in entry_point:
        return None
    module_name, attr = entry_point.strip().rsplit(":", 1)
    # 允许相对 skill_dir 的模块路径
    module_path = skill_dir / f"{module_name.replace('.', '/')}.py"
    if not module_path.exists():
        # 尝试 skill_dir 下单文件
        module_path = skill_dir / (module_name.split(".")[-1] + ".py")
    if not module_path.exists():
        return None
    skill_dir_str = str(skill_dir.resolve())
    if skill_dir_str not in sys.path:
        sys.path.insert(0, skill_dir_str)
    spec = importlib.util.spec_from_file_location(f"skill_{skill_dir.name}", module_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, attr.strip(), None)


def _make_http_tool(name: str, description: str, config: dict[str, Any] | None) -> Callable[..., str]:
    def http_tool(url: str | None = None, method: str = "GET", body: str | None = None) -> str:
        target = (url or (config or {}).get("url") or "").strip()
        if not target:
            return "Error: missing url"
        m = (method or "GET").upper()
        try:
            with httpx.Client(timeout=30.0) as client:
                if m == "GET":
                    r = client.get(target)
                elif m == "POST":
                    r = client.post(target, content=body)
                else:
                    return f"Unsupported method: {m}"
                return f"Status: {r.status_code}\n{r.text[:2000]}"
        except Exception as e:
            return f"Request failed: {e!s}"

    http_tool.__name__ = name.replace(" ", "_")
    http_tool.__doc__ = description or "Call an HTTP endpoint."
    return http_tool


def load_skill_from_path(skills_root: Path, source_path: str) -> Callable[..., Any] | None:
    """
    从 skills 根目录下的 source_path 加载技能，返回可被 Agent 使用的 Callable。
    source_path 为相对 skills_root 的子目录名（或相对路径）。
    """
    skill_dir = (skills_root / source_path).resolve()
    if not skill_dir.is_dir():
        return None
    manifest = parse_skill_manifest(skill_dir)
    if not manifest:
        return None
    name = str(manifest.get("name") or skill_dir.name).strip()
    description = str(manifest.get("description") or "")
    skill_type = str(manifest.get("type") or "python").lower()
    config = manifest.get("config")
    if not isinstance(config, dict):
        config = {}

    if skill_type == "python":
        entry_point = manifest.get("entry_point")
        if not entry_point:
            # 常见约定：skill.py 或 index.py 中的 tool / skill / run
            for mod_name, attr in [("skill", "tool"), ("skill", "skill"), ("index", "tool")]:
                fn = _load_python_entry_point(skill_dir, f"{mod_name}:{attr}")
                if callable(fn):
                    if not getattr(fn, "__name__", None):
                        fn.__name__ = name.replace(" ", "_")
                    if not getattr(fn, "__doc__", None):
                        fn.__doc__ = description
                    return fn
            return None
        fn = _load_python_entry_point(skill_dir, entry_point)
        if callable(fn):
            if not getattr(fn, "__name__", None):
                fn.__name__ = name.replace(" ", "_")
            if not getattr(fn, "__doc__", None):
                fn.__doc__ = description
            return fn
        return None

    if skill_type == "http":
        return _make_http_tool(name, description, config)
    return None


def clone_github_skill(repo_url: str, skills_root: Path) -> str:
    """
    将 GitHub 仓库克隆到 skills_root 下，返回克隆后的子目录名。
    repo_url 可为 https://github.com/owner/repo 或 owner/repo。
    """
    skills_root.mkdir(parents=True, exist_ok=True)
    url = repo_url.strip()
    if not url.startswith(("https://", "http://", "git@")):
        url = f"https://github.com/{url}.git"
    elif not url.endswith(".git"):
        url = url.rstrip("/") + ".git"
    # 子目录名：取 repo 名，避免重复则加 owner
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if match:
        owner, repo = match.group(1), match.group(2).replace(".git", "")
        subdir = f"{owner}_{repo}"
    else:
        subdir = url.split("/")[-1].replace(".git", "") or "repo"
    target = skills_root / subdir
    if target.exists():
        # 已存在则拉取更新
        subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=target,
            capture_output=True,
            timeout=60,
            check=False,
        )
        return subdir
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git clone failed: {result.stderr or result.stdout or 'unknown'}")
    return subdir


def _safe_skill_dest_name(repo_slug: str, skill_folder: str) -> str:
    """生成落地到项目 skills/ 下的技能目录名，避免与现有目录冲突。"""
    # 使用双下划线便于分割：owner_repo__skill
    raw = f"{repo_slug}__{skill_folder}"
    safe = re.sub(r"[^a-zA-Z0-9_\\-\\.]+", "_", raw)
    return safe[:120] if len(safe) > 120 else safe


def import_github_repo_skills(repo_url: str, skills_root: Path) -> list[str]:
    """
    将 GitHub 仓库中 `skills/` 目录下的所有技能子目录复制到当前项目 skills/ 下。

    - 一个 GitHub 项目可能包含多个技能：repo/skills/<skill1>, repo/skills/<skill2> ...
    - 每个子目录都会被复制为 skills/<owner_repo>__<skill> 这样的独立技能目录（可单独开关）。

    返回复制后的技能目录名列表（相对 skills_root）。
    """
    skills_root.mkdir(parents=True, exist_ok=True)
    repo_cache_root = skills_root / ".github_repos"
    repo_cache_root.mkdir(parents=True, exist_ok=True)

    repo_slug = clone_github_skill(repo_url, repo_cache_root)
    repo_dir = repo_cache_root / repo_slug

    repo_skills_dir = repo_dir / "skills"
    if not repo_skills_dir.is_dir():
        raise RuntimeError("GitHub 仓库缺少 skills/ 目录，请确保仓库内存在 skills/<skill>/skill.yaml 或 SKILL.md")

    imported: list[str] = []
    for child in repo_skills_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        dest_name = _safe_skill_dest_name(repo_slug, child.name)
        dest_dir = skills_root / dest_name
        # 若已存在则覆盖更新（保持统一来源）；用于仓库更新后重新导入
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(child, dest_dir)
        imported.append(dest_name)

    if not imported:
        raise RuntimeError("skills/ 目录下未发现任何技能子目录")
    return imported


def discover_local_skills(skills_root: Path) -> list[dict[str, Any]]:
    """扫描 skills_root 下所有包含 skill.yaml 的子目录，返回 manifest 列表。"""
    if not skills_root.is_dir():
        return []
    out = []
    for path in skills_root.iterdir():
        if not path.is_dir():
            continue
        if path.name.startswith("."):
            continue
        manifest = parse_skill_manifest(path)
        if manifest:
            manifest["source_path"] = path.name
            manifest.setdefault("name", path.name)
            manifest.setdefault("source_type", "local")
            out.append(manifest)
    return out
