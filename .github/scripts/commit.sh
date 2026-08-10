#!/usr/bin/env bash
# 取得結果をコミットして push する。
# 3つのワークフローが同じブランチへ push するため、競合したら rebase して再試行する。
set -euo pipefail

MESSAGE="${1:?コミットメッセージが必要}"
BRANCH="${GITHUB_REF_NAME:-main}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add -A data article

if git diff --cached --quiet; then
  echo "変更なし。コミットしない。"
  exit 0
fi

git commit -m "${MESSAGE}"

for attempt in 1 2 3 4 5; do
  if git push origin "HEAD:${BRANCH}"; then
    echo "push 成功"
    exit 0
  fi
  echo "push 失敗（${attempt}回目）。rebase して再試行する。"
  sleep $((attempt * 3))
  git pull --rebase origin "${BRANCH}"
done

echo "push できなかった" >&2
exit 1
