#!/usr/bin/env python3
"""Initialize the repository-local project memory skeleton."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


MEMORY_RELATIVE = Path(".codex/docs/memory")
MEMORY_ENTRY = ".codex/docs/memory/MEMORY.md"
MANAGED_START = "<!-- manage-project-memory:start -->"


def absolute_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--repo-root 必须是绝对路径")
    path = path.resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"目录不存在: {path}")
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


def integrate_agents(repo_root: Path, snippet_path: Path) -> str:
    agents_path = repo_root / "AGENTS.md"
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    if MANAGED_START in existing or MEMORY_ENTRY in existing:
        return "preserved"

    snippet = snippet_path.read_text(encoding="utf-8").strip()
    if existing.strip():
        content = existing.rstrip() + "\n\n" + snippet + "\n"
    else:
        content = snippet + "\n"
    agents_path.write_text(content, encoding="utf-8")
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=absolute_directory)
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parent.parent
    template_root = skill_root / "assets" / "memory-zh"
    repo_root: Path = args.repo_root
    memory_root = repo_root / MEMORY_RELATIVE

    results = [
        (MEMORY_RELATIVE / "MEMORY.md", write_template(template_root / "MEMORY.md", memory_root / "MEMORY.md")),
        (
            MEMORY_RELATIVE / "topic_template.md",
            write_template(template_root / "topic_template.md", memory_root / "topic_template.md"),
        ),
    ]
    for name in ("topics", "inbox", "dreams"):
        results.append((MEMORY_RELATIVE / name / ".gitkeep", ensure_gitkeep(memory_root / name)))

    agents_status = integrate_agents(repo_root, template_root / "agents_section.md")
    results.append((Path("AGENTS.md"), agents_status))

    for path, status in results:
        print(f"[{status.upper()}] {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
