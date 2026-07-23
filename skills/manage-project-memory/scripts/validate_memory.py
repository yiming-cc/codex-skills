#!/usr/bin/env python3
"""Validate the repository-local project memory structure."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path


DEFAULT_MEMORY_RELATIVE = Path(".codex/docs/memory")
REQUIRED_FILES = ("MEMORY.md", "topic_template.md")
REQUIRED_DIRECTORIES = ("topics", "inbox", "dreams")
TOPIC_SECTIONS = (
    "稳定记忆",
    "检索提示",
    "证据引用",
    "已知失败模式",
    "最近验证",
    "过期 / 不要推断",
)
PLACEHOLDERS = (
    "<Topic 名称>",
    "<stable_snake_case_id>",
    "<一句话说明该 topic 在什么任务中相关>",
    "<具体任务意图>",
    "<明确不应触发的相邻任务>",
    "核验后首个非空行以与 frontmatter 相同",
)
FORBIDDEN_TOPIC_SECTIONS = ("范围", "触发词")
INDEX_ENTRY = re.compile(r"^-\s+`(?P<path>topics/[^`]+\.md)`\s*$")
TOPIC_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRONTMATTER_FIELDS = (
    "id",
    "description",
    "positive_triggers",
    "negative_triggers",
    "paths",
    "status",
    "last_verified",
)
LIST_FIELDS = ("positive_triggers", "negative_triggers", "paths")
TOPIC_STATUSES = {"active", "needs_review", "deprecated"}


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


def parse_frontmatter(text: str) -> tuple[dict[str, object], str, str | None]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text, "缺少文件开头的 YAML frontmatter"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, text, "YAML frontmatter 缺少结束分隔符 `---`"

    metadata: dict[str, object] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line[:1].isspace():
            return {}, text, "frontmatter 必须是扁平字段，列表使用 JSON 风格行内数组"
        key, separator, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()
        if not separator or not key or not raw_value:
            return {}, text, f"无法解析 frontmatter 行: {line}"
        if key in metadata:
            return {}, text, f"frontmatter 字段重复: {key}"
        if raw_value == "null":
            value: object = None
        elif raw_value.startswith(('"', "[")):
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as error:
                return {}, text, f"frontmatter 字段 `{key}` 不是有效 JSON/YAML 值: {error.msg}"
        else:
            value = raw_value
        metadata[key] = value

    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return metadata, body, None


def section_text(body: str, section: str) -> str:
    marker = f"## {section}"
    lines = body.splitlines()
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return ""
    end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def primary_verified_date(body: str) -> str | None:
    for line in section_text(body, "最近验证").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:$|[：:\s])", stripped)
        return match.group(1) if match else None
    return None


def topic_index_paths(memory_text: str) -> list[str]:
    paths: list[str] = []
    for line in section_text(memory_text, "Topic 索引").splitlines():
        match = INDEX_ENTRY.match(line)
        if match:
            paths.append(Path(match.group("path")).as_posix())
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=absolute_directory)
    parser.add_argument("--memory-root", type=relative_directory, default=DEFAULT_MEMORY_RELATIVE)
    args = parser.parse_args()

    repo_root: Path = args.repo_root
    memory_relative: Path = args.memory_root
    memory_root = (repo_root / memory_relative).resolve()
    if repo_root not in memory_root.parents:
        parser.error("--memory-root 解析后必须位于仓库内且不能等于仓库根目录")
    errors: list[str] = []
    warnings: list[str] = []

    if not memory_root.is_dir():
        errors.append(f"缺少 memory 目录: {memory_relative.as_posix()}")
    for name in REQUIRED_FILES:
        if not (memory_root / name).is_file():
            errors.append(f"缺少核心文件: {(memory_relative / name).as_posix()}")
    for name in REQUIRED_DIRECTORIES:
        if not (memory_root / name).is_dir():
            errors.append(f"缺少核心目录: {(memory_relative / name).as_posix()}")

    memory_path = memory_root / "MEMORY.md"
    memory_text = memory_path.read_text(encoding="utf-8") if memory_path.is_file() else ""
    indexed_paths = topic_index_paths(memory_text)
    indexed_counts = Counter(indexed_paths)

    if memory_text:
        if "## Topic 索引" not in memory_text:
            errors.append("MEMORY.md 缺少 `## Topic 索引` 章节")
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

    topic_ids: list[str] = []
    for topic_path in topic_files:
        relative = topic_path.relative_to(memory_root).as_posix()
        text = topic_path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"topic 文件为空: {relative}")
            continue
        metadata, body, frontmatter_error = parse_frontmatter(text)
        if frontmatter_error:
            errors.append(f"topic frontmatter 无效: {relative}: {frontmatter_error}")
            body = text
        else:
            missing_fields = [field for field in FRONTMATTER_FIELDS if field not in metadata]
            unknown_fields = sorted(set(metadata) - set(FRONTMATTER_FIELDS))
            if missing_fields:
                errors.append(f"topic frontmatter 缺少字段: {relative}: {', '.join(missing_fields)}")
            if unknown_fields:
                errors.append(f"topic frontmatter 含未知字段: {relative}: {', '.join(unknown_fields)}")

            topic_id = metadata.get("id")
            if not isinstance(topic_id, str) or not TOPIC_ID.fullmatch(topic_id):
                errors.append(f"topic frontmatter `id` 必须是 snake_case: {relative}")
            else:
                topic_ids.append(topic_id)

            description = metadata.get("description")
            if not isinstance(description, str) or not description.strip() or "\n" in description:
                errors.append(f"topic frontmatter `description` 必须是单行非空字符串: {relative}")

            for field in LIST_FIELDS:
                value = metadata.get(field)
                if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                    errors.append(f"topic frontmatter `{field}` 必须是字符串数组: {relative}")
                elif field == "positive_triggers" and not value:
                    errors.append(f"topic frontmatter `positive_triggers` 不能为空: {relative}")
                elif len(value) != len(set(value)):
                    errors.append(f"topic frontmatter `{field}` 含重复项: {relative}")

            paths = metadata.get("paths")
            if isinstance(paths, list):
                for path_hint in paths:
                    if not isinstance(path_hint, str):
                        continue
                    hint = Path(path_hint)
                    if hint.is_absolute() or ".." in hint.parts or "\\" in path_hint:
                        errors.append(f"topic frontmatter `paths` 含非法仓库路径: {relative}: {path_hint}")

            status = metadata.get("status")
            if not isinstance(status, str) or status not in TOPIC_STATUSES:
                errors.append(f"topic frontmatter `status` 无效: {relative}: {status}")

            verified = metadata.get("last_verified")
            body_verified = primary_verified_date(body)
            if verified is None:
                if status == "active":
                    errors.append(f"active topic 的 `last_verified` 不能为空: {relative}")
                if body_verified is not None:
                    errors.append(
                        f"frontmatter `last_verified` 为 null，但正文最近验证含主日期: {relative}: {body_verified}"
                    )
            elif not isinstance(verified, str):
                errors.append(f"topic frontmatter `last_verified` 必须是 ISO 日期或 null: {relative}")
            elif not ISO_DATE.fullmatch(verified):
                errors.append(f"topic frontmatter `last_verified` 必须使用 YYYY-MM-DD: {relative}: {verified}")
            else:
                try:
                    verified_date = date.fromisoformat(verified)
                except ValueError:
                    errors.append(f"topic frontmatter `last_verified` 不是有效 ISO 日期: {relative}: {verified}")
                else:
                    if verified_date > date.today():
                        errors.append(f"topic frontmatter `last_verified` 不能是未来日期: {relative}: {verified}")
                    if verified != body_verified:
                        errors.append(
                            f"frontmatter `last_verified` 与正文最近验证主日期不一致: "
                            f"{relative}: frontmatter={verified} body={body_verified}"
                        )
            if status == "needs_review":
                warnings.append(f"topic 标记为 needs_review，使用前必须重新核验: {relative}")

        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                errors.append(f"topic 含未替换模板占位符: {relative}: {placeholder}")
        body_lines = body.splitlines()
        for section in FORBIDDEN_TOPIC_SECTIONS:
            if f"## {section}" in body_lines:
                errors.append(f"topic 正文含已由 frontmatter 取代的章节 `{section}`: {relative}")
        section_positions: list[int] = []
        for section in TOPIC_SECTIONS:
            try:
                position = body_lines.index(f"## {section}")
            except ValueError:
                warnings.append(f"topic 缺少推荐章节 `{section}`: {relative}")
            else:
                section_positions.append(position)
        if section_positions != sorted(section_positions):
            errors.append(f"topic 推荐章节顺序错误: {relative}")
        line_count = len(text.splitlines())
        if line_count > 120:
            warnings.append(f"topic 共 {line_count} 行，建议压缩或拆分: {relative}")

    for topic_id, count in sorted(Counter(topic_ids).items()):
        if count > 1:
            errors.append(f"topic frontmatter `id` 重复: {topic_id}")

    agents_path = repo_root / "AGENTS.md"
    if not agents_path.is_file():
        warnings.append("根目录缺少 AGENTS.md，后续 agent 可能无法自动发现 memory")
    else:
        memory_entry = (memory_relative / "MEMORY.md").as_posix()
        if memory_entry not in agents_path.read_text(encoding="utf-8"):
            warnings.append(f"AGENTS.md 未引用 `{memory_entry}`")

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
