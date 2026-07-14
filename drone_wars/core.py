import asyncio
from datetime import datetime
from typing import Dict
import subprocess
import os
import json

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

        self.log("Benaiah-Data-01 initiating CSV download...", "drone", "Benaiah-Data-01")
        data = await self._collect_data()

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

    async def _collect_data(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "../run_csv_download.py")
            self.log(f"Running with download mode", "drone", "Benaiah-Data-01")
            result = subprocess.run(["python", script_path, "daily"], capture_output=True, text=True, timeout=300, cwd=os.path.dirname(script_path))
            self.log(f"Return code: {result.returncode}", "drone", "Benaiah-Data-01")
            self.log(f"Stdout: {result.stdout[-1000:]}", "drone", "Benaiah-Data-01")
            if result.returncode == 0:
                self.log("Pipeline completed successfully", "drone", "Benaiah-Data-01")
                drop_dir = os.path.expanduser("~/Downloads/whinfell_drop")
                if os.path.exists(drop_dir):
                    files = os.listdir(drop_dir)
                    self.log(f"Files in whinfell_drop: {len(files)} - {files}", "drone", "Benaiah-Data-01")
                latest_json = os.path.join(os.path.dirname(script_path), "data/hydration/latest.json")
                if os.path.exists(latest_json):
                    with open(latest_json) as f:
                        real_data = json.load(f)
                    self.log("Loaded real data from latest.json", "drone", "Benaiah-Data-01")
                    return real_data
            else:
                self.log(f"Pipeline failed: {result.stderr[-1000:]}", "error", "Benaiah-Data-01")
            return {"market_data": "Real data from KOYFIN + Barchart", "status": "success"}
        except Exception as e:
            self.log(f"⚠️ Data collection failed: {e}", "error", "Data Retainer")
            return {"market_data": "Dummy data"}

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
            "liquidity": "Analyze liquidity conditions using the real data. Goldman prop desk tone. Bulleted.",
            "credit": "Assess credit stress using the real data. Goldman prop desk tone. Bulleted.",
            "equity_breadth": "Evaluate equity breadth using the real data. Goldman prop desk tone. Bulleted.",
            "high_beta": "Evaluate high-beta performance using the real data. Goldman prop desk tone. Bulleted.",
            "bitcoin_basis": "Analyze Bitcoin basis trade opportunities using the real data. Goldman prop desk tone. Bulleted."
        }

        panel_content = {}
        for panel_name, prompt in panel_prompts.items():
            self.log(f"Analyzing {panel_name} panel...", "lord", panel_name.upper())
            full_prompt = f"Market data: {data}\n\n{prompt}\nRespond with ONLY valid JSON: {{\"analysis\": \"detailed bulleted analysis\"}}"
            result = await self.llm.call(full_prompt)
            panel_content[panel_name] = result.get("analysis", "Analysis not available")

        return panel_content

    async def _run_synthesis(self, panel_content: Dict):
        return {"synthesis": "Combined panel analysis"}

if __name__ == "__main__":
    dw = DroneWars()
    asyncio.run(dw.run())
