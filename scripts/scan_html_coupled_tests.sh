#!/usr/bin/env bash
# P0-T1: 扫描 pytest 中直接耦合 static/*.html 或 static/js/ 的测试文件
# 产物：.omc/plans/html-coupled-tests.txt
# 背景：前端重构后 static/ 将迁到 /legacy/，任何直接断言 static 路径的测试必须改写
#
# 用法：bash scripts/scan_html_coupled_tests.sh
# 期望：输出 9 个 test_v07_*.py 文件

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${REPO_ROOT}/.omc/plans/html-coupled-tests.txt"

mkdir -p "$(dirname "$OUT")"

# grep pattern 覆盖:
#   - static/*.html (任意 .html 引用)
#   - static/js/ (JS 资源引用)
grep -rln --include='*.py' --exclude-dir='__pycache__' \
  -E 'static/.*\.html|static/js/' "${REPO_ROOT}/tests/" \
  | sort -u > "$OUT"

COUNT=$(wc -l < "$OUT" | tr -d ' ')
echo "P0-T1 扫描完成: 耦合测试文件数 = ${COUNT}"
echo "清单已写入: ${OUT}"

# 期望闸门：应为 9
EXPECTED=9
if [ "$COUNT" -ne "$EXPECTED" ]; then
  echo "⚠️  闸门警告: 期望 ${EXPECTED} 个文件，实测 ${COUNT} 个" >&2
  echo "    若 > ${EXPECTED}: 可能新增了 HTML 耦合测试，需重审工期" >&2
  echo "    若 < ${EXPECTED}: 可能测试被删除或重构，需核实 plan 清单" >&2
  exit 1
fi

echo "✅ 闸门通过: 与 plan 预期吻合"
