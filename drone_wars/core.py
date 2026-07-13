import asyncio
from datetime import datetime
from typing import Dict

from models.llm_client import LLMClient

class DroneWars:
    def __init__(self):
        self.llm = LLMClient()
        self.logs = []

    def log(self, message: str, level: str = "system", actor: str = "SYSTEM"):
        entry = {
            "actor": actor,
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.logs.append(entry)
        print(f"{actor}: {message}")

    def get_logs(self):
        return self.logs

    async def run(self):
        self.logs.clear()
        self.log("🔄 Refresh Data initiated by user", "system")

        data = {"market_data": "BTC basis trade data from CME futures and spot ETFs"}

        self.log("Sovereign analyzing fresh market data...", "sovereign", "SOVEREIGN")
        sovereign_result = await self._run_sovereign(data)

        panel_content = await self._run_panel_analysis(data)

        self.log("🧠 Lord Jephthah synthesizing...", "synthesis", "SYNTHESIS")
        await self._run_synthesis(panel_content)

        self.log("✅ Full Drone Wars cycle completed successfully", "system")
        return {
            "panel_content": panel_content,
            "summary": sovereign_result.get("market_summary", "")
        }

    async def _run_sovereign(self, data: Dict) -> Dict:
        prompt = f"""Market data: {data}

Provide a brief, professional market summary.
Output ONLY valid JSON:
{{"market_summary": "one sentence summary"}}
"""
        result = await self.llm.call(prompt)
        self.log(f"Market Summary: {result.get('market_summary', 'No summary available')}", "sovereign", "SOVEREIGN")
        return result

    async def _run_panel_analysis(self, data: Dict) -> Dict:
        panel_prompts = {
            "liquidity": "Analyze liquidity conditions.",
            "credit": "Assess credit stress.",
            "equity_breadth": "Evaluate equity breadth.",
            "high_beta": "Evaluate high-beta performance.",
            "bitcoin_basis": "Analyze Bitcoin basis trade opportunities."
        }

        panel_content = {}
        for panel_name, prompt in panel_prompts.items():
            self.log(f"Analyzing {panel_name} panel...", "lord", panel_name.upper())
            full_prompt = f"Market data: {data}\n\n{prompt}\nRespond with ONLY valid JSON: {{\"analysis\": \"detailed analysis\"}}"
            result = await self.llm.call(full_prompt)
            panel_content[panel_name] = result.get("analysis", "Analysis not available")

        return panel_content

    async def _run_synthesis(self, panel_content: Dict):
        return {"synthesis": "Combined panel analysis"}

if __name__ == "__main__":
    dw = DroneWars()
    asyncio.run(dw.run())
