from __future__ import annotations


def generate_hypotheses(experiments: list[dict]) -> list[str]:
    if not experiments:
        return ["先补齐样本质量；当前还没有可参考的实验历史。"]
    hypotheses = []
    latest = experiments[0]
    metrics = latest["metrics"]
    if metrics["trade_count"] < 20:
        hypotheses.append("提高交易数：放宽支撑跌破和首次卖压阈值搜索范围。")
    if metrics["slippage_cost"] > metrics["net_return"]:
        hypotheses.append("降低滑点压力：候选标的向盘口更深的币种收敛。")
    if metrics["max_drawdown"] < -0.12:
        hypotheses.append("降低回撤：缩短最大持仓并收紧移动止损。")
    return hypotheses or ["在新的 validation 窗口复测当前最佳配置。"]
