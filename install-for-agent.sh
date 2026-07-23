#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_dir/skills"
timestamp="$(date +%Y%m%d%H%M%S)"

# Known agents in display order. Each resolves to a target skills directory via
# resolve_target() below. Defaults follow each agent's own <HOME>/skills convention.
known_agents=(codex zcode agents claude cursor)

# Resolve an agent name to its target skills directory.
# Returns 0 and prints the path on success, returns 1 on unknown agent.
resolve_target() {
  case "$1" in
    codex)  printf '%s/skills' "${CODEX_HOME:-$HOME/.codex}" ;;
    zcode)  printf '%s/skills' "${ZCODE_HOME:-$HOME/.zcode}" ;;
    agents) printf '%s/skills' "${AGENTS_HOME:-$HOME/.agents}" ;;
    claude) printf '%s/skills' "${CLAUDE_HOME:-$HOME/.claude}" ;;
    cursor) printf '%s/skills' "${CURSOR_HOME:-$HOME/.cursor}" ;;
    *) return 1 ;;
  esac
}

# Human-readable hint for the trailing "restart" message, per agent.
restart_hint() {
  case "$1" in
    codex)  echo "Restart Codex, or start a new task, if newly linked skills are not visible yet." ;;
    zcode)  echo "Restart your ZCode session if newly linked skills are not visible yet." ;;
    agents) echo "Restart any agent that scans ~/.agents/skills if newly linked skills are not visible yet." ;;
    claude) echo "Restart Claude Code if newly linked skills are not visible yet." ;;
    cursor) echo "Restart Cursor if newly linked skills are not visible yet." ;;
  esac
}

usage() {
  cat <<'USAGE'
Usage: install-for-agent.sh [options]

Install every skill under skills/ into one or more agents' skills directories by
delegating to bootstrap.sh. The default action is an interactive multi-select
menu; pass --agent to skip the menu.

Options:
  --agent NAME      Install for agent NAME (repeatable). Skips the interactive menu.
                    Known agents: codex, zcode, agents, claude, cursor.
  --list            Print known agents and their resolved target paths, then exit.
  --keep-existing   Keep existing same-named skills in the target directory (default).
                    Passed through to bootstrap.sh.
  --overwrite       Replace existing same-named skills with the repo version.
                    Old skills are moved to a backup directory first.
                    Passed through to bootstrap.sh.
  -h, --help        Show this help.

Environment:
  CODEX_HOME, ZCODE_HOME, AGENTS_HOME, CLAUDE_HOME, CURSOR_HOME
  Override each agent's home directory (defaults: ~/.codex, ~/.zcode, ~/.agents,
  ~/.claude, ~/.cursor). Each agent's skills are installed under <home>/skills.

If no --agent is given, an interactive multi-select menu is shown. Enter
comma-separated numbers and/or names (e.g. 1,3 or zcode,agents or 1,zcode).
Empty input exits without installing anything.

USAGE
}

# --- Parse CLI ------------------------------------------------------------

selected=()
install_mode="keep"
list_only=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agent)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--agent requires a name" >&2
        exit 1
      fi
      selected+=("$1")
      ;;
    --list)
      list_only=1
      ;;
    --keep-existing|--keep)
      install_mode="keep"
      ;;
    --overwrite)
      install_mode="overwrite"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

case "$install_mode" in
  keep|overwrite) ;;
  *)
    echo "invalid install mode: $install_mode" >&2
    exit 1
    ;;
esac

# --- Validate agent names from --agent -----------------------------------

validate_name() {
  local name="$1"
  for a in "${known_agents[@]}"; do
    if [ "$a" = "$name" ]; then
      return 0
    fi
  done
  return 1
}

for name in "${selected[@]:-}"; do
  if [ -n "$name" ] && ! validate_name "$name"; then
    echo "unknown agent: $name" >&2
    echo "known agents: ${known_agents[*]}" >&2
    exit 1
  fi
done

# --- --list ---------------------------------------------------------------

if [ "$list_only" -eq 1 ]; then
  printf '%-8s %s\n' "AGENT" "TARGET"
  for a in "${known_agents[@]}"; do
    target="$(resolve_target "$a")"
    printf '%-8s %s\n' "$a" "$target"
  done
  exit 0
fi

# --- Interactive menu if no --agent given ---------------------------------

if [ "${#selected[@]}" -eq 0 ]; then
  echo "Known agents:"
  i=1
  for a in "${known_agents[@]}"; do
    target="$(resolve_target "$a")"
    note=""
    [ "$a" = "agents" ] && note="  (cross-tool shared path)"
    printf '  %d) %-8s %s%s\n' "$i" "$a" "$target" "$note"
    i=$((i + 1))
  done
  echo
  echo "Select agents to install (comma-separated numbers or names, e.g. 1,3 or zcode,agents)."
  echo "Empty input exits without installing."

  attempt=0
  max_attempts=3
  while [ "$attempt" -lt "$max_attempts" ]; do
    attempt=$((attempt + 1))
    printf 'Selection: '
    read -r input || input=""
    [ -z "$input" ] && {
      echo "No agents selected."
      exit 0
    }

    # Split on comma and/or whitespace.
    IFS=', 	' read -r -a tokens <<<"$input"

    bad=""
    selected=()
    for tok in "${tokens[@]}"; do
      [ -z "$tok" ] && continue
      name=""
      if [[ "$tok" =~ ^[0-9]+$ ]]; then
        idx="$tok"
        if [ "$idx" -ge 1 ] && [ "$idx" -le "${#known_agents[@]}" ]; then
          name="${known_agents[$((idx - 1))]}"
        fi
      else
        if validate_name "$tok"; then
          name="$tok"
        fi
      fi
      if [ -z "$name" ]; then
        bad="$bad $tok"
      else
        # Deduplicate while preserving order.
        dup=0
        for s in "${selected[@]:-}"; do
          [ "$s" = "$name" ] && { dup=1; break; }
        done
        [ "$dup" -eq 0 ] && selected+=("$name")
      fi
    done

    if [ -n "$bad" ]; then
      echo "Unknown entries:$bad. Known agents: ${known_agents[*]}." >&2
      [ "$attempt" -ge "$max_attempts" ] && {
        echo "Too many invalid attempts. Exiting." >&2
        exit 1
      }
      continue
    fi

    if [ "${#selected[@]}" -eq 0 ]; then
      echo "No agents selected."
      exit 0
    fi
    break
  done
fi

# --- Sanity checks --------------------------------------------------------

if [ ! -d "$source_dir" ]; then
  echo "missing skills directory: $source_dir" >&2
  exit 1
fi

if [ ! -x "$repo_dir/bootstrap.sh" ] && [ ! -f "$repo_dir/bootstrap.sh" ]; then
  echo "missing bootstrap.sh next to this script: $repo_dir/bootstrap.sh" >&2
  exit 1
fi

# --- Install for each selected agent -------------------------------------

overwrite_flag=""
[ "$install_mode" = "overwrite" ] && overwrite_flag="--overwrite"

summary=()
for agent in "${selected[@]}"; do
  if ! target="$(resolve_target "$agent")"; then
    echo "unknown agent: $agent" >&2
    exit 1
  fi

  echo "=== Installing for agent: $agent -> $target ==="
  # bootstrap.sh is agent-agnostic via --target-dir; we reuse all of its
  # idempotency, backup, and output conventions. We suppress bootstrap.sh's own
  # trailing "Restart Codex" line (it is hardcoded to Codex) and emit an
  # agent-appropriate hint ourselves below. The summary line above it is kept.
  # shellcheck disable=SC2086
  set +e
  bash "$repo_dir/bootstrap.sh" \
        --target-dir "$target" \
        ${overwrite_flag} \
    | sed '\|^Restart Codex, or start a new task|d'
  rc="${PIPESTATUS[0]}"
  set -e
  if [ "$rc" -eq 0 ]; then
    summary+=("$agent: ok ($target)")
  else
    summary+=("$agent: FAILED ($target)")
  fi
  restart_hint "$agent"
  echo
done

echo "=== Summary ==="
for line in "${summary[@]}"; do
  echo "  $line"
done
