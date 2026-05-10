def run_backtest(prompt: str | None = None) -> str:
    task = (prompt or "").strip()

    return (
        "📈 Strategy (AI idea):\n"
        f"Requested task: {task or 'No task provided'}\n\n"
        "⚡ Optimized Result:\n"
        "Backtest engine hook is connected in Orion.\n"
        "This endpoint is ready for your real optimizer/backtest module.\n\n"
        "🔥 Profit: N/A"
    )