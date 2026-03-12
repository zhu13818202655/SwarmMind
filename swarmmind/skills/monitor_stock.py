"""Monitor Stock Skill - Fetch stock data, analyze, and send alerts."""

from typing import Any
from swarmmind.skills.base import Skill, SkillResult


class MonitorStockSkill(Skill):
    """Skill for monitoring stock prices."""

    name = "monitor_stock"
    description = "Monitor stock prices and send alerts"

    def __init__(self, http_tool=None, mail_tool=None):
        super().__init__()
        self._http_tool = http_tool
        self._mail_tool = mail_tool

    def get_parameters_schema(self) -> dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock symbols to monitor",
                },
                "threshold": {
                    "type": "number",
                    "description": "Price change threshold percentage",
                },
                "alert_email": {
                    "type": "string",
                    "description": "Email to send alerts to",
                },
                "source": {
                    "type": "string",
                    "enum": ["yahoo", "alpha_vantage", "mock"],
                    "default": "mock",
                    "description": "Data source",
                },
            },
            "required": ["symbols"],
        }

    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill."""
        symbols = kwargs.get("symbols", [])
        threshold = kwargs.get("threshold", 5.0)
        alert_email = kwargs.get("alert_email")
        source = kwargs.get("source", "mock")

        if not symbols:
            return SkillResult(success=False, error="Symbols are required")

        try:
            # Step 1: Fetch stock data
            stock_data = await self._fetch_stock_data(symbols, source)

            # Step 2: Analyze
            alerts = self._analyze(stock_data, threshold)

            # Step 3: Send alert if needed
            if alerts and alert_email and self._mail_tool:
                alert_msg = self._format_alerts(alerts)
                await self._mail_tool(
                    to=alert_email,
                    subject="Stock Alert",
                    body=alert_msg,
                )

            return SkillResult(
                success=True,
                output={
                    "stocks": stock_data,
                    "alerts": alerts,
                },
                metadata={"steps": ["fetch", "analyze", "alert"]},
            )

        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _fetch_stock_data(self, symbols: list[str], source: str) -> list[dict]:
        """Fetch stock data."""
        if source == "mock":
            # Return mock data for testing
            return [
                {"symbol": s, "price": 100.0 + i * 10, "change": 2.5}
                for i, s in enumerate(symbols)
            ]

        # Real data fetching would go here
        # For now, use mock data
        return []

    def _analyze(self, stock_data: list[dict], threshold: float) -> list[dict]:
        """Analyze stock data for alerts."""
        alerts = []
        for stock in stock_data:
            if abs(stock.get("change", 0)) >= threshold:
                alerts.append({
                    "symbol": stock["symbol"],
                    "price": stock["price"],
                    "change": stock["change"],
                    "reason": "Threshold exceeded",
                })
        return alerts

    def _format_alerts(self, alerts: list[dict]) -> str:
        """Format alerts as email body."""
        lines = ["Stock Price Alerts:\n"]
        for alert in alerts:
            lines.append(
                f"- {alert['symbol']}: ${alert['price']:.2f} "
                f"(change: {alert['change']:.2f}%)"
            )
        return "\n".join(lines)
