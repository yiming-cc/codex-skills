#!/usr/bin/env python3
"""Initialize the repository-local project memory skeleton."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_MEMORY_RELATIVE = Path(".codex/docs/memory")
MANAGED_START = "<!-- manage-project-memory:start -->"
MANAGED_END = "<!-- manage-project-memory:end -->"


def absolute_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--repo-root 必须是绝对路径")
    path = path.resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"目录不存在: {path}")
    return path


def relative_directory(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("--memory-root 必须是仓库内的相对路径")
    if not path.parts or path == Path("."):
        raise argparse.ArgumentTypeError("--memory-root 不能为空")
    return path


def write_template(source: Path, destination: Path) -> str:
    if destination.exists() and destination.stat().st_size > 0:
        return "preserved"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return "created"


def ensure_gitkeep(directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    gitkeep = directory / ".gitkeep"
    if gitkeep.exists():
        return "preserved"
    gitkeep.touch()
    return "created"


def validate_agents_target(repo_root: Path, memory_entry: str, parser: argparse.ArgumentParser) -> None:
    agents_path = repo_root / "AGENTS.md"
    if not agents_path.exists():
        return
    existing = agents_path.read_text(encoding="utf-8")
    if MANAGED_START not in existing:
        return
    start = existing.index(MANAGED_START)
    end = existing.find(MANAGED_END, start)
    if end < 0:
        parser.error("AGENTS.md 中的 manage-project-memory managed block 缺少结束标记")
    managed_block = existing[start : end + len(MANAGED_END)]
    if memory_entry not in managed_block:
        parser.error(
            "AGENTS.md 已声明另一 memory root；请先明确迁移或继续使用现有入口，避免创建第二套 memory"
        )


def integrate_agents(repo_root: Path, snippet_path: Path, memory_entry: str) -> str:
    agents_path = repo_root / "AGENTS.md"
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    if MANAGED_START in existing or memory_entry in existing:
        return "preserved"

    snippet = snippet_path.read_text(encoding="utf-8").replace("{{memory_entry}}", memory_entry).strip()
    if existing.strip():
        content = existing.rstrip() + "\n\n" + snippet + "\n"
    else:
        content = snippet + "\n"
    agents_path.write_text(content, encoding="utf-8")
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=absolute_directory)
    parser.add_argument("--memory-root", type=relative_directory, default=DEFAULT_MEMORY_RELATIVE)
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parent.parent
    template_root = skill_root / "assets" / "memory-zh"
    repo_root: Path = args.repo_root
    memory_relative: Path = args.memory_root
    memory_root = (repo_root / memory_relative).resolve()
    if repo_root not in memory_root.parents:
        parser.error("--memory-root 解析后必须位于仓库内且不能等于仓库根目录")
    memory_entry = (memory_relative / "MEMORY.md").as_posix()
    validate_agents_target(repo_root, memory_entry, parser)

    results = [
        (memory_relative / "MEMORY.md", write_template(template_root / "MEMORY.md", memory_root / "MEMORY.md")),
        (
            memory_relative / "topic_template.md",
            write_template(template_root / "topic_template.md", memory_root / "topic_template.md"),
        ),
    ]
    for name in ("topics", "inbox", "dreams"):
        results.append((memory_relative / name / ".gitkeep", ensure_gitkeep(memory_root / name)))

    agents_status = integrate_agents(repo_root, template_root / "agents_section.md", memory_entry)
    results.append((Path("AGENTS.md"), agents_status))

    for path, status in results:
        print(f"[{status.upper()}] {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
