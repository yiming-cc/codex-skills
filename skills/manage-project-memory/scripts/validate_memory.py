#!/usr/bin/env python3
"""Validate the repository-local project memory structure."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


MEMORY_RELATIVE = Path(".codex/docs/memory")
REQUIRED_FILES = ("MEMORY.md", "topic_template.md")
REQUIRED_DIRECTORIES = ("topics", "inbox", "dreams")
TOPIC_SECTIONS = (
    "范围",
    "触发词",
    "稳定记忆",
    "检索提示",
    "证据引用",
    "已知失败模式",
    "最近验证",
    "过期 / 不要推断",
)
PLACEHOLDERS = (
    "<Topic 名称>",
    "说明这个记忆文件用于指导哪类任务。",
    "列出应触发 agent 打开该 topic",
)
INDEX_ROW = re.compile(r"^\|\s*`(?P<path>topics/[^`]+\.md)`\s*\|")


def absolute_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--repo-root 必须是绝对路径")
    path = path.resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"目录不存在: {path}")
    return path


def topic_index_paths(memory_text: str) -> list[str]:
    paths: list[str] = []
    for line in memory_text.splitlines():
        match = INDEX_ROW.match(line)
        if match:
            paths.append(Path(match.group("path")).as_posix())
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=absolute_directory)
    args = parser.parse_args()

    repo_root: Path = args.repo_root
    memory_root = repo_root / MEMORY_RELATIVE
    errors: list[str] = []
    warnings: list[str] = []

    if not memory_root.is_dir():
        errors.append(f"缺少 memory 目录: {MEMORY_RELATIVE.as_posix()}")
    for name in REQUIRED_FILES:
        if not (memory_root / name).is_file():
            errors.append(f"缺少核心文件: {(MEMORY_RELATIVE / name).as_posix()}")
    for name in REQUIRED_DIRECTORIES:
        if not (memory_root / name).is_dir():
            errors.append(f"缺少核心目录: {(MEMORY_RELATIVE / name).as_posix()}")

    memory_path = memory_root / "MEMORY.md"
    memory_text = memory_path.read_text(encoding="utf-8") if memory_path.is_file() else ""
    indexed_paths = topic_index_paths(memory_text)
    indexed_counts = Counter(indexed_paths)

    if memory_text:
        if "## Topic 文件" not in memory_text:
            errors.append("MEMORY.md 缺少 `## Topic 文件` 路由章节")
        if len(memory_text.splitlines()) > 200:
            warnings.append(f"MEMORY.md 共 {len(memory_text.splitlines())} 行，入口可能过于膨胀")

    for path, count in sorted(indexed_counts.items()):
        if count > 1:
            errors.append(f"MEMORY.md 重复索引 topic: {path}")
        candidate = (memory_root / path).resolve()
        topics_root = (memory_root / "topics").resolve()
        if topics_root not in candidate.parents:
            errors.append(f"topic 索引越出 topics 目录: {path}")
        elif not candidate.is_file():
            errors.append(f"topic 索引指向不存在的文件: {path}")

    topics_root = memory_root / "topics"
    topic_files = sorted(topics_root.rglob("*.md")) if topics_root.is_dir() else []
    actual_paths = {path.relative_to(memory_root).as_posix() for path in topic_files}
    for path in sorted(actual_paths - set(indexed_paths)):
        errors.append(f"topic 未登记到 MEMORY.md: {path}")

    for topic_path in topic_files:
        relative = topic_path.relative_to(memory_root).as_posix()
        text = topic_path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"topic 文件为空: {relative}")
            continue
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                errors.append(f"topic 含未替换模板占位符: {relative}: {placeholder}")
        for section in TOPIC_SECTIONS:
            if f"## {section}" not in text:
                warnings.append(f"topic 缺少推荐章节 `{section}`: {relative}")
        line_count = len(text.splitlines())
        if line_count > 120:
            warnings.append(f"topic 共 {line_count} 行，建议压缩或拆分: {relative}")

    agents_path = repo_root / "AGENTS.md"
    if not agents_path.is_file():
        warnings.append("根目录缺少 AGENTS.md，后续 agent 可能无法自动发现 memory")
    elif ".codex/docs/memory/MEMORY.md" not in agents_path.read_text(encoding="utf-8"):
        warnings.append("AGENTS.md 未引用 `.codex/docs/memory/MEMORY.md`")

    for message in errors:
        print(f"[ERROR] {message}")
    for message in warnings:
        print(f"[WARNING] {message}")
    print(
        f"[SUMMARY] topics={len(topic_files)} indexed={len(indexed_paths)} "
        f"errors={len(errors)} warnings={len(warnings)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
