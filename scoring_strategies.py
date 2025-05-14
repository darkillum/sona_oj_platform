# sonar_oj_platform_project_root/scoring_strategies.py
import re
import json


def default_log_scorer(log_content: str, submission_obj=None, problem_obj=None):
    """
    默认的日志评分器:
    - 检查判题辅助脚本 (runner) 是否成功完成。
    - 对错误进行扣分。
    - 提取用户通过 `[USER_METRIC]` 标签输出的指标。
    """
    score = 0.0
    details = {"notes": [], "metrics": {}, "errors_found_in_log": 0, "raw_score_before_clamp": 0.0}

    if not log_content:
        details["notes"].append("日志内容为空或不可用。")
        return 0.0, details

    # 检查判题辅助脚本是否成功完成
    runner_completed_match = re.search(r"\[Runner Script End\].*Exit Code: 0", log_content, re.IGNORECASE)
    runner_processed_chunks_match = re.search(r"\[Runner\] Final count: (\d+) chunks processed", log_content,
                                              re.IGNORECASE)

    if runner_completed_match:
        score += 50  # 成功执行的基础分
        details["notes"].append("算法判题辅助脚本成功完成 (退出码 0)。")
        if runner_processed_chunks_match:
            try:
                chunks = int(runner_processed_chunks_match.group(1))
                details["metrics"]["chunks_processed_by_runner"] = chunks
                if chunks == 0 and submission_obj and submission_obj.return_code == 0:  # 成功退出但处理0块数据可能意味着问题
                    details["notes"].append("警告: 判题辅助脚本成功退出，但处理了 0 个数据块。")
                    score -= 10
            except ValueError:
                details["notes"].append("警告: 无法从日志中解析判题辅助脚本处理的数据块数量。")
    else:
        details["notes"].append("算法判题辅助脚本未能成功完成或退出码非零。")
        score -= 30  # 较大惩罚

    # 对判题辅助脚本或系统报告的错误进行扣分
    system_errors = re.findall(
        r"\[Runner\] CRITICAL:|\[Runner\] ERROR|\[EVALUATION_SYSTEM\] Error|\[Runner Main\] Unhandled exception",
        log_content, re.IGNORECASE)
    details["errors_found_in_log"] = len(system_errors)
    if details["errors_found_in_log"] > 0:
        score -= details["errors_found_in_log"] * 15
        details["notes"].append(f"在系统/判题辅助脚本日志中发现 {details['errors_found_in_log']} 个严重错误。")

    # 提取用户定义的指标
    # 匹配格式: [USER_METRIC] KeyName: 123.45  或 [USER_METRIC] Key-Name: -1.2e3
    user_metrics_found = re.findall(r"\[USER_METRIC\]\s*([\w_.-]+):\s*([-\d\.eE+]+)", log_content)
    for key, value_str in user_metrics_found:
        try:
            value = float(value_str)
            details["metrics"][key] = value
            # 示例：根据提取的指标添加特定的评分逻辑
            if problem_obj and problem_obj.title == 'Sonar Echo Counter' and key == 'Total_Echoes':
                if value > 0: score += min(value * 0.5, 30)  # 回声越多分数越高，上限30分
                details["notes"].append(f"统计到的回声数量: {value}")
            elif problem_obj and problem_obj.title == 'Stream Anomaly Detector' and key == 'Anomalies_Found':
                if value > 0: score += min(value * 2, 40)  # 异常点越多分数越高，上限40分
                details["notes"].append(f"发现的异常点数量: {value}")
            # 可以为其他题目和指标添加更多 elif 条件
        except ValueError:
            details["metrics"][key] = value_str  # 如果不是浮点数，则按字符串存储
            details["notes"].append(f"发现非数值类型的用户指标 '{key}': {value_str}")

    if not user_metrics_found and runner_completed_match:
        details["notes"].append("判题辅助脚本已完成，但未找到用于特定评分的 [USER_METRIC] 标签。")

    details["raw_score_before_clamp"] = round(score, 2)
    final_score = max(0.0, min(100.0, score))  # 将分数限制在 0 到 100 之间

    return round(final_score, 2), details


# --- 在此注册你的评分函数 ---
SCORING_FUNCTIONS = {
    "default_log_scorer": default_log_scorer,
    # "advanced_sonar_scorer": advanced_sonar_function, # 示例：可以添加更高级的评分器
}


def get_scoring_function(name: str):
    """根据名称获取评分函数。"""
    return SCORING_FUNCTIONS.get(name, default_log_scorer)  # 如果找不到，则回退到默认评分器