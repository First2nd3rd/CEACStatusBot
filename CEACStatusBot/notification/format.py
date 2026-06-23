"""Human-readable formatting for CEAC status notifications, including a
comparison against the previously recorded status.

The current status dict may carry the previous record under ``result["previous"]``
(a dict like ``{"status": ..., "last_updated": ..., "date": ...}``) or ``None``
when there is no history yet. A dict with ``success`` set to False renders a
"query failed" heartbeat instead.
"""


def _is_failure(result: dict) -> bool:
    return result.get("success") is False


def _is_changed(result: dict) -> bool:
    previous = result.get("previous")
    if not previous:
        return True
    return (
        previous.get("status") != result.get("status")
        or previous.get("last_updated") != result.get("case_last_updated")
    )


def build_subject(result: dict) -> str:
    app = result.get("application_num_origin") or result.get("application_num", "")
    if _is_failure(result):
        return f"[美签状态] {app}:⚠️ 查询失败"
    if not result.get("previous"):
        tag = "首次记录"
    elif _is_changed(result):
        tag = "状态有变化!"
    else:
        tag = "无变化"
    return f"[美签状态] {app}:{result.get('status', '?')}（{tag}）"


def _comparison_block(result: dict) -> list[str]:
    previous = result.get("previous")
    cur_status = result.get("status", "")
    cur_updated = result.get("case_last_updated", "")

    if not previous:
        return [
            "上次:（无历史记录,这是第一次记录)",
            f"本次:{cur_status}(最后更新 {cur_updated})",
            "结论:首次记录,暂无可对比的历史状态。",
        ]

    prev_status = previous.get("status", "?")
    prev_updated = previous.get("last_updated", "?")
    lines = [
        f"上次:{prev_status}(最后更新 {prev_updated})",
        f"本次:{cur_status}(最后更新 {cur_updated})",
    ]
    if prev_status == cur_status and prev_updated == cur_updated:
        lines.append(f"结论:状态无变化,仍为「{cur_status}」。")
    else:
        changes = []
        if prev_status != cur_status:
            changes.append(f"状态 {prev_status} → {cur_status}")
        if prev_updated != cur_updated:
            changes.append(f"最后更新 {prev_updated} → {cur_updated}")
        lines.append("结论:⚠️ 检测到变化! " + ";".join(changes))
    return lines


REASON_ZH = {
    "wrong_captcha": "验证码连续识别失败",
    "blocked": "疑似被 CEAC 拦截(HTTP 403)",
    "rate_limited": "请求过于频繁被限流(HTTP 429)",
    "server_error": "CEAC 服务器故障或维护",
    "http_error": "CEAC 返回异常响应",
    "empty_page": "页面异常,疑似被拦截或服务中断",
    "no_status": "页面未返回状态,可能验证码错或网站改版",
    "captcha_missing": "验证码图片缺失,疑似被拦截或网站改版",
    "location_missing": "页面结构异常,疑似被拦截或网站改版",
    "case_mismatch": "返回的申请号与查询不一致",
    "date_missing": "拿到状态但缺少日期,疑似网站改版",
    "network_timeout": "网络超时(CEAC 较慢或你的网络/代理)",
    "connection_failed": "连接失败(网络/代理/DNS,不一定是被封)",
    "config": "配置有误,请检查 LOCATION 设置",
    "unknown": "未知错误",
}


def _failure_body(result: dict) -> str:
    sep = "=" * 42
    lines = [
        "美国签证状态查询失败 (CEAC NIV)",
        sep,
        "",
        f"申请号  :{result.get('application_num_origin', '')}",
        f"查询时间:{result.get('time', '')}",
    ]
    reason_zh = REASON_ZH.get(result.get("reason_key"))
    if reason_zh:
        lines.append(f"可能原因:{reason_zh}")
    lines += [
        "",
        "本次自动查询未能成功(可能是 CEAC 临时不可用、验证码连续识别失败或网络问题)。",
        "工具仍在运行,会在下一个计划时间自动重试。",
        "如果连续多天收到此邮件,请检查 logs/visacheck.log。",
        "",
        sep,
        "本邮件由本地 visacheck 工具自动发送。",
    ]
    return "\n".join(lines)


def build_body(result: dict) -> str:
    if _is_failure(result):
        return _failure_body(result)

    sep = "=" * 42
    lines = [
        "美国签证状态查询结果 (CEAC NIV)",
        sep,
        "",
        f"申请号  :{result.get('application_num', '')}",
        f"签证类型:{result.get('visa_type', '')}",
        f"当前状态:{result.get('status', '')}",
        f"递交日期:{result.get('case_created', '')}",
        f"最后更新:{result.get('case_last_updated', '')}",
        f"查询时间:{result.get('time', '')}",
        "",
        "—— 与上次对比 ——",
        *_comparison_block(result),
        "",
        "—— 领事系统原文说明 ——",
        result.get("description", "") or "",
        "",
        sep,
        "本邮件由本地 visacheck 工具自动发送。",
    ]
    return "\n".join(lines)
