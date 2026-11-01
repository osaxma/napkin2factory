#!/bin/sh
# One trunk, a folder per task: `make task`, `make land`, `make tasks`, `make abandon`.
# Why: S-097 (the flow), S-098 (hardlinked environments), S-099 (ids in every commit).
#
#   task.sh new <slug> <goal>   branch task/<slug> in .worktrees/<slug>, from main
#   task.sh land                rebase onto main, assign journal ids, gate, fast-forward main
#   task.sh list                every open task folder: goal, progress, unsaved changes
#   task.sh abandon <slug>      drop a task folder and its branch (needs CONFIRM=1)
#
# Plain git and POSIX sh, for any agent or person. For this script's tests only:
# N2F_TASK_NO_SYNC=1 skips `uv sync`, LAND_GATE=none skips the gate.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)

die() {
  printf 'task: %s\n' "$*" >&2
  exit 1
}

# The folder that has main checked out (where tasks land and `make check` runs).
primary() {
  git worktree list --porcelain | awk '
    /^worktree / { wt = substr($0, 10) }
    $0 == "branch refs/heads/main" { print wt; exit }'
}

dirty() {
  [ -n "$(git -C "$1" status --porcelain)" ]
}

cmd_new() {
  slug=${1:-}
  goal=${2:-}
  case $slug in
    '' | -* | *[!a-z0-9-]*) die "give a short name of lowercase letters, digits and dashes: make task NAME=fix-cost-bands GOAL=\"...\"" ;;
  esac
  [ -n "$goal" ] || die "say what the task is for in one line: make task NAME=$slug GOAL=\"...\""
  [ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "start tasks from the folder that has main checked out ($(primary))"
  top=$(git rev-parse --show-toplevel)
  git -C "$top" check-ignore -q .worktrees/x || die "add .worktrees/ to .gitignore first"
  git show-ref --verify --quiet "refs/heads/task/$slug" && die "task/$slug already exists: pick another name, or see make tasks"
  git worktree add -q "$top/.worktrees/$slug" -b "task/$slug" main
  git config "branch.task/$slug.description" "$goal"
  if [ -z "${N2F_TASK_NO_SYNC:-}" ]; then
    # Hardlinks, not uv's macOS default of clones: macOS scans every new native library on its
    # first load (~3 min for this environment); hardlinked files are the cache's own, so the scan
    # happens once per package version, not once per task folder (S-098).
    (cd "$top/.worktrees/$slug" && UV_LINK_MODE=${UV_LINK_MODE:-hardlink} "${UV:-uv}" sync -q)
    # The first CAD-kernel import still takes a few seconds (S-057); start it now, detached, so
    # it is done by the time the task first builds. N2F_NO_WARMUP=1 skips it.
    if [ -z "${N2F_NO_WARMUP:-}" ]; then
      (cd "$top/.worktrees/$slug" && nohup "${UV:-uv}" run python -c "import build123d" >/dev/null 2>&1 &)
    fi
  fi
  cat <<EOF
Task folder: $top/.worktrees/$slug (branch task/$slug)
Goal: $goal
Next:
  cd $top/.worktrees/$slug
  work and commit there (stopping unfinished? commit with a subject starting "WIP: ")
  make land        when done, from that folder
EOF
}

cmd_land() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ] &&
    die "a rebase is in progress: fix the conflicted files, git add them, git rebase --continue, then make land again"
  branch=$(git rev-parse --abbrev-ref HEAD)
  case $branch in
    main) die "you are on main: run make land inside a task folder (see make tasks)" ;;
    HEAD) die "no branch checked out here: run make land inside a task folder (see make tasks)" ;;
  esac
  dirty . && die "unsaved changes here: commit them (or remove them), then make land again"
  main_dir=$(primary)
  [ -n "$main_dir" ] || die "no folder has main checked out: check out main in the primary folder"
  if git log --format=%s "main..HEAD" | grep -q '^WIP'; then
    die "commits marked WIP are on $branch: finish them, then fold them into one commit
  (this branch is unpushed, so rewriting it is fine): git reset --soft main && git commit"
  fi
  # Each attempt starts again from the task's own commits, placeholders intact: if main moved
  # (another task landed), ids given out against the old main may now be taken (S-102).
  start=$(git rev-parse HEAD)
  tries=0
  while :; do
    tries=$((tries + 1))
    git reset -q --hard "$start"
    if ! git rebase -q main; then
      die "the rebase onto main stopped on a conflict (it is still in progress).
  Fix the conflicted files (git status lists them), git add them, git rebase --continue,
  then make land again. To give up the rebase instead: git rebase --abort"
    fi
    python3 "$HERE/journal_ids.py" --base main
    case ${LAND_GATE:-fast} in
      fast) "${MAKE:-make}" lint types &&
        N2F_ALLOW_PLACEHOLDERS=0 "${UV:-uv}" run pytest tests/unit/test_journals.py tests/unit/test_agent_docs.py -q ||
        die "the landing checks failed: fix, commit, then make land again" ;;
      check) N2F_ALLOW_PLACEHOLDERS=0 "${MAKE:-make}" check || die "make check failed: fix, commit, then make land again" ;;
      none) ;;
      *) die "LAND_GATE is fast (default), check or none, not '$LAND_GATE'" ;;
    esac
    dirty "$main_dir" && die "the main folder $main_dir has unsaved changes: they must be committed or removed there first"
    count=$(git rev-list --count main..HEAD)
    landed=
    for wait in 1 2 3; do
      git -C "$main_dir" merge -q --ff-only "$branch" 2>/dev/null && landed=1 && break
      git merge-base --is-ancestor main HEAD || break  # main moved: rebase again
      sleep "$wait"  # main has not moved: another landing holds git's lock for a moment
    done
    [ -n "$landed" ] && break
    git merge-base --is-ancestor main HEAD &&
      die "could not fast-forward main in $main_dir: git merge --ff-only $branch there shows why"
    [ "$tries" -lt 3 ] || die "main kept moving (another task landed) three times: run make land again"
    echo "main moved while landing; starting again from this task's own commits"
  done
  here=$(git rev-parse --show-toplevel)
  cd "$main_dir"
  case $here in
    "$main_dir"/.worktrees/*)
      git worktree remove "$here"
      git branch -q -d "$branch"
      gone="removed $here and branch $branch; cd $main_dir" ;;
    *) gone="this folder was not made by make task: remove it with the tool that made it" ;;
  esac
  echo "Landed $count commit(s) from $branch; main is now $(git rev-parse --short main)."
  echo "$gone"
  echo "Run make check in $main_dir before pushing."
}

cmd_list() {
  main_dir=$(primary)
  if [ -z "$main_dir" ]; then
    main_dir=$(git worktree list --porcelain | sed -n '1s/^worktree //p')
    echo "note: no folder has main checked out; tasks start from and land on one that does"
  fi
  [ -n "$(git worktree list --porcelain | grep '^worktree ' | sed 1d)" ] || echo "no open tasks"
  git worktree list --porcelain | awk '
    /^worktree / { wt = substr($0, 10) }
    /^branch refs\/heads\// { print substr($0, 19) "\t" wt }' |
    while IFS="$(printf '\t')" read -r branch dir; do
      [ "$dir" = "$main_dir" ] && continue
      goal=$(git config "branch.$branch.description" || echo "no goal recorded")
      state=clean
      dirty "$dir" && state="UNSAVED CHANGES"
      printf '%s  (%s)\n' "${branch#task/}" "$dir"
      printf '  goal:    %s\n' "$goal"
      printf '  ahead:   %s commit(s) not on main; %s\n' "$(git rev-list --count "main..$branch")" "$state"
      printf '  newest:  %s (%s)\n' "$(git log -1 --format=%s "$branch")" "$(git log -1 --format=%cr "$branch")"
    done
}

cmd_abandon() {
  slug=${1:-}
  [ -n "$slug" ] || die "name the task: make abandon NAME=<slug> CONFIRM=1 (see make tasks)"
  main_dir=$(primary)
  dir="$main_dir/.worktrees/$slug"
  branch="task/$slug"
  git show-ref --verify --quiet "refs/heads/$branch" || die "no branch $branch (see make tasks)"
  echo "Abandoning $branch would lose these commits not on main:"
  git log --format='  %h %s' "main..$branch"
  [ -d "$dir" ] && dirty "$dir" && echo "and unsaved changes in $dir:" && git -C "$dir" status --short
  [ "${CONFIRM:-}" = 1 ] || die "nothing removed; to go ahead: make abandon NAME=$slug CONFIRM=1"
  cd "$main_dir"
  [ -d "$dir" ] && git worktree remove --force "$dir"
  git branch -q -D "$branch"
  echo "Removed $dir and $branch."
}

case ${1:-} in
  new) shift && cmd_new "$@" ;;
  land) cmd_land ;;
  list) cmd_list ;;
  abandon) shift && cmd_abandon "$@" ;;
  *) die "usage: task.sh new <slug> <goal> | land | list | abandon <slug>" ;;
esac
