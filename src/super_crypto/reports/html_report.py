from __future__ import annotations

import html
from pathlib import Path

from super_crypto.common.paths import ensure_parent


def render_html_report(path: Path, context: dict) -> str:
    ensure_parent(path)
    metrics = context["metrics"]
    rows = "".join(
        f"<tr><td>{html.escape(row['symbol'])}</td><td>{row['trade_count']}</td><td>{row['net_return']:.2%}</td></tr>"
        for row in context["symbol_breakdown"]
    )
    signals = "".join(
        f"<li>{html.escape(signal['symbol'])} {html.escape(signal['strategy'])} {html.escape(signal['signal_time'])}</li>"
        for signal in context["signals"][:20]
    )
    content = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Experiment {html.escape(context['experiment_id'])}</title>
        <style>
          body {{ background:#0b0e11; color:#eaecef; font-family: Arial, sans-serif; padding:32px; }}
          table {{ border-collapse: collapse; width: 100%; }}
          td, th {{ border:1px solid #2b3139; padding:8px; text-align:left; }}
          .metric {{ display:inline-block; margin-right:24px; }}
        </style>
      </head>
      <body>
        <h1>Experiment {html.escape(context['experiment_id'])}</h1>
        <div class="metric">Strategy: {html.escape(context['strategy'])}</div>
        <div class="metric">Split: {html.escape(context['split'])}</div>
        <div class="metric">Net return: {metrics['net_return']:.2%}</div>
        <div class="metric">Sharpe: {metrics['sharpe']:.2f}</div>
        <h2>By Symbol</h2>
        <table><thead><tr><th>Symbol</th><th>Trades</th><th>Net Return</th></tr></thead><tbody>{rows}</tbody></table>
        <h2>Signals</h2>
        <ul>{signals}</ul>
      </body>
    </html>
    """
    path.write_text(content, encoding="utf-8")
    return str(path)

