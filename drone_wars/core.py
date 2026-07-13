import asyncio
from datetime import datetime
from typing import Dict
import subprocess
import os
import sys
from pathlib import Path
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
            base_dir = Path(__file__).resolve().parent.parent
            script_path = base_dir / "run_csv_download.py"
            
            self.log(f"Running: python {script_path} daily", "drone", "Benaiah-Data-01")
            
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{base_dir}:{base_dir}/whinfell_pipeline:{python_path}".rstrip(":")
            
            result = subprocess.run(
                [sys.executable, str(script_path), "daily"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=base_dir,
                env=env
            )
            
            self.log(f"Return code: {result.returncode}", "drone", "Benaiah-Data-01")
            
            if result.returncode == 0:
                self.log("CSV download completed successfully", "drone", "Benaiah-Data-01")
                
                # Look for generated files
                manifest_dir = base_dir / "staged_raw" / "manifests"
                csv_dir = base_dir / "data"
                manifests = list(manifest_dir.glob("*.json")) if manifest_dir.exists() else []
                
                market_data = f"Processed {len(manifests)} manifests, {len(list(csv_dir.glob('*.csv')))} CSVs"
                
                return {
                    "market_data": market_data,
                    "status": "success",
                    "manifests": len(manifests)
                }
            else:
                self.log(f"CSV download failed: {result.stderr[-800:]}", "error", "Benaiah-Data-01")
                return {"market_data": "CSV download failed", "status": "error"}
                
        except Exception as e:
            self.log(f"⚠️ Data collection failed: {str(e)}", "error", "Data Retainer")
            return {"market_data": "Error during collection", "status": "error"}

    async def _run_sovereign(self, data: Dict) -> Dict:
        prompt = f"""Market data summary: {data.get('market_data', 'No data')}
Provide a brief, professional market summary.
Output ONLY valid JSON:
{{"market_summary": "one sentence summary"}}
"""
        result = await self.llm.call(prompt)
        self.log(f"Market Summary: {result.get('market_summary', 'No summary')}", "sovereign", "SOVEREIGN")
        return result

    async def _run_panel_analysis(self, data: Dict) -> Dict:
        panel_prompts = {
            "liquidity": "Analyze liquidity conditions. Goldman prop desk tone. Bulleted.",
            "credit": "Assess credit stress. Goldman prop desk tone. Bulleted.",
            "equity_breadth": "Evaluate equity breadth. Goldman prop desk tone. Bulleted.",
            "high_beta": "Evaluate high-beta performance. Goldman prop desk tone. Bulleted.",
            "bitcoin_basis": "Analyze Bitcoin basis trade opportunities. Goldman prop desk tone. Bulleted."
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
