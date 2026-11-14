#!/usr/bin/env bash
# 重新导出当前会话的完整对话记录并放到 chatlog/ 下。
# 用法：bash tools/update_chatlog.sh
set -e
cd "$(dirname "$0")/.."
python tools/export_chatlog.py
cp "$TEMP/ocean_dm_results/chatlog/AI_CONVERSATION.md" chatlog/
echo "已更新 chatlog/AI_CONVERSATION.md"
echo "--- 自检 ---"
python tools/check.py || { echo "自检未通过：先修问题再提交"; exit 1; }
