from __future__ import annotations

from pathlib import Path

from super_crypto.common.paths import ensure_parent


def render_markdown_report(path: Path, context: dict) -> str:
    ensure_parent(path)
    metrics = context["metrics"]
    lines = [
        f"# Experiment {context['experiment_id']}",
        "",
        f"- Strategy: {context['strategy']}",
        f"- Engine: {context['engine']}",
        f"- Split: {context['split']}",
        f"- Net return: {metrics['net_return']:.2%}",
        f"- Sharpe: {metrics['sharpe']:.2f}",
        f"- Max drawdown: {metrics['max_drawdown']:.2%}",
        f"- Trade count: {metrics['trade_count']}",
        f"- Top 5 removed net return: {metrics['top5_removed_net_return']:.2%}",
        "",
        "## Signals",
        "",
    ]
    for signal in context["signals"][:20]:
        reason = ", ".join(signal["reason"])
        lines.append(
            f"- {signal['symbol']} {signal['strategy']} {signal['signal_time']} "
            f"| confidence {signal['confidence']:.2f} | {reason}"
        )
    lines.extend(["", "## By Symbol", ""])
    for row in context["symbol_breakdown"]:
        lines.append(f"- {row['symbol']}: net {row['net_return']:.2%}, trades {row['trade_count']}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
