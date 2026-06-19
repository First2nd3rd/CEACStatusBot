#!/bin/bash
# Quick health check: are the visacheck scheduled jobs loaded, and did they run?
UID_NUM="$(id -u)"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"

echo "===== 1) 是否已开启(出现任务名 = 开着)====="
if launchctl list | grep visacheck; then
    echo "  -> 已加载。三列 = PID | 上次退出码 | 任务名 (PID 为 - 是正常的)"
else
    echo "  -> 未找到,说明没开。运行: bash scheduling/install.sh"
fi

echo ""
echo "===== 2) 每个任务的运行情况 ====="
for label in com.visacheck.poll com.visacheck.summary; do
    echo "  [$label]"
    launchctl print "gui/${UID_NUM}/${label}" 2>/dev/null \
        | grep -iE "state =|runs =|last exit code" | sed 's/^/    /' \
        || echo "    (未加载)"
done

echo ""
echo "===== 3) 最近一次运行的日志 ====="
if [ -s "$REPO/logs/visacheck.log" ]; then
    echo "  日志最后修改: $(stat -f '%Sm' "$REPO/logs/visacheck.log")"
    tail -n 8 "$REPO/logs/visacheck.log" | sed 's/^/    /'
else
    echo "  (日志为空 —— 还没到计划时间跑过,或刚重装)"
fi

echo ""
echo "===== 4) 上次记录到的状态时间 ====="
[ -f "$REPO/status_record.json" ] && echo "  status_record.json 最后修改: $(stat -f '%Sm' "$REPO/status_record.json")" || echo "  (无记录)"
