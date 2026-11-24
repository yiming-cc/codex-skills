#!/usr/bin/env python3
"""Initialize project memory and the Agent work document directories."""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

SKILL = Path(__file__).absolute().parents[1]
MEMORY_SCRIPTS = SKILL.parent / "manage-project-memory" / "scripts"
DEFAULT_TOPIC = Path("topics/agent_work_documents.md")
HARD_RULE = "- 只有用户在当前请求中明确要求编写或更新 Agent 工作文档时，才创建相应文档目录、编写或更新文档。"
LEGACY_PARAGRAPH = (
    "Agent 工作文档统一放在 `.agent/` 下。实验文档放入 `.agent/experiments/YYYY-MM-DD_<name>/`，"
    "计划文档放入 `.agent/plan/YYYY-MM-DD_<name>/`，目录命名和文档组织规则见 "
    "[`.agent/README.md`](.agent/README.md)。新项目可调用 `$project-setup` 一键初始化该结构。"
)
LEGACY_SECTION = "<!-- project-setup:agent-docs -->\n## Agent 文档目录约定\n\n" + LEGACY_PARAGRAPH
WORK_DOCUMENT_READMES = {
    ".agent/README.md": """# Agent 工作文档

- `doc/` 存放项目理解说明，例如架构、配置、流程和模块关系。
- `experiments/YYYY-MM-DD_<name>/` 存放实验细节和验收文档。
- `plan/YYYY-MM-DD_<name>/` 存放计划、任务拆解和计划验收文档。
- `memory/` 存放项目长期记忆，入口见 `memory/MEMORY.md`。

初始化只建立目录和用途说明。具体工作文档按用户要求写入对应目录。
""",
    ".agent/doc/README.md": """# 项目理解说明

本目录用于保存可复用的项目理解文档，包括架构、配置、流程、模块关系和维护说明。

写入或更新说明前，先核对当前代码和配置，并在文档中保留证据路径。临时日志、实验结果和任务计划分别放入实验或计划目录。
""",
    ".agent/experiments/README.md": """# 实验文档

每个实验使用独立目录 `.agent/experiments/YYYY-MM-DD_<name>/`。实验细节和验收结论分开保存，后续记录沿用同一主题目录。
""",
    ".agent/plan/README.md": """# 计划文档

每个计划使用独立目录 `.agent/plan/YYYY-MM-DD_<name>/`。计划可记录目标、任务拆解、阶段安排、里程碑、进度和风险，计划验收文档放在同一目录。
""",
}
# Digests of the three unmodified READMEs emitted by the previous initializer.
LEGACY_READMES = {
    ".agent/README.md": "f173125c88dd7cea385df07e89fe92bfe9ca6c589bf0332c87ceb66342c6538f",
    ".agent/experiments/README.md": "31dc5a13e56fe624ea23b4b8131bedaabe312ed649624f304b0f22fd9e3e48cb",
    ".agent/plan/README.md": "743793dd5f192777beb371f263dfc75f44f4d64f6f487702da16286cae072449",
}


def relative_path(path):
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ValueError(f"Expected a repository-relative path: {path}")
    return path


def memory_root(repo, requested):
    agents = repo / "AGENTS.md"
    guidance = agents.read_text() if agents.is_file() else ""
    block = re.search(r"<!-- manage-project-memory:start -->(.*?)<!-- manage-project-memory:end -->",
                      guidance, re.DOTALL)
    roots = {Path(value).parent for value in
             re.findall(r"[`(]([^()`\n]+/MEMORY\.md)[`)]", block[1] if block else guidance)}
    if not roots:
        roots = {Path(p) for p in (".agent/memory", ".codex/docs/memory")
                 if (repo / p / "MEMORY.md").is_file()}
    if requested:
        root = relative_path(requested)
        if roots and root not in roots:
            raise ValueError(f"Requested root {root} conflicts with {roots}")
        return root
    if len(roots) > 1:
        raise ValueError(f"Multiple memory entries found: {roots}. Specify --memory-root.")
    return relative_path(next(iter(roots), Path(".agent/memory")))


def add_entry(text, heading, entry):
    lines = text.splitlines(keepends=True)
    start = next((i + 1 for i, line in enumerate(lines) if line.rstrip() == heading), None)
    if start is None:
        raise ValueError(f"Missing memory section: {heading}")
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    if entry in (line.strip() for line in lines[start:end]):
        return text
    first = start
    while first < end and not lines[first].strip():
        first += 1
    if first == end:
        lines[start:end] = ["\n", entry + "\n", "\n"]
    else:
        lines.insert(first, entry + "\n")
    return "".join(lines)


def run_memory(script, repo, root, display_repo):
    result = subprocess.run(
        [sys.executable, str(MEMORY_SCRIPTS / script), "--repo-root", str(repo), "--memory-root", str(root)],
        capture_output=True, text=True,
    )
    for output in (result.stdout, result.stderr):
        if output:
            print(output.replace(str(repo), str(display_repo)), end="")
    if result.returncode:
        raise SystemExit(result.returncode)


def initialize_work_document_dirs(repo):
    for name, content in WORK_DOCUMENT_READMES.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content)
            print(f"create {name}")


def setup(repo, root, topic, display_repo):
    if topic != DEFAULT_TOPIC and not (repo / root / topic).is_file():
        raise ValueError(f"Existing topic not found: {topic}")
    for script in ("init_memory.py", "validate_memory.py"):
        if not (MEMORY_SCRIPTS / script).is_file():
            raise ValueError(f"Missing manage-project-memory dependency: {MEMORY_SCRIPTS / script}")
    run_memory("init_memory.py", repo, root, display_repo)
    entry = repo / root / "MEMORY.md"
    before = entry.read_text()
    updated = add_entry(before, "## 硬规则", HARD_RULE)
    updated = add_entry(updated, "## Topic 索引", f"- `{topic.as_posix()}`")
    topic_file = repo / root / topic
    if not topic_file.exists():
        template = (SKILL / "assets/agent_work_documents.md").read_text()
        topic_file.write_text(template.replace("{{date}}", date.today().isoformat()))
        print(f"create {root / topic}")
    if updated != before:
        entry.write_text(updated)
        print(f"update {root / 'MEMORY.md'}")
    run_memory("validate_memory.py", repo, root, display_repo)
    initialize_work_document_dirs(repo)

    agents = repo / "AGENTS.md"
    before = agents.read_text()
    cleaned = re.sub(r"(?m)^(?:" + re.escape(LEGACY_SECTION) + "|" + re.escape(LEGACY_PARAGRAPH)
                     + r")$(?:\n\n?)?", "", before)
    if cleaned != before:
        agents.write_text(cleaned)
        print("remove legacy document guidance from AGENTS.md")
    for name, digest in LEGACY_READMES.items():
        path = repo / name
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                path.unlink()
                print(f"remove {name}")
            else:
                print(f"preserve customized {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="preview changes in a temporary copy")
    parser.add_argument("--memory-root", type=Path)
    parser.add_argument("--topic", type=Path, default=DEFAULT_TOPIC, help="existing topic relative to the memory root")
    args = parser.parse_args()
    repo = args.project_root.expanduser().resolve()
    if not repo.is_dir():
        parser.error(f"project directory not found: {repo}")
    try:
        root = memory_root(repo, args.memory_root)
        topic = relative_path(args.topic)
        if topic.parts[0] != "topics" or topic.suffix != ".md":
            raise ValueError(f"Expected a Markdown topic under topics/: {topic}")
        if args.dry_run:
            print(f"Preview for {repo}")
            with TemporaryDirectory() as tmp:
                preview = Path(tmp)
                if (repo / root).is_dir():
                    shutil.copytree(repo / root, preview / root)
                for name in ("AGENTS.md", *LEGACY_READMES, *WORK_DOCUMENT_READMES):
                    if (repo / name).is_file():
                        (preview / name).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(repo / name, preview / name)
                setup(preview, root, topic, repo)
        else:
            setup(repo, root, topic, repo)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
