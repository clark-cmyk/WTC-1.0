from enum import Enum
from typing import List, Dict, Any
import asyncio

from models.grok_client import call_grok_api
from models.deepseek_client import call_drone_api
from agents.captain_prompts import get_captain_prompt
from agents.orchestrator_prompt import get_orchestrator_prompt

class AgentType(Enum):
    ABADDON = "Abaddon"
    GOLIATH = "Goliath"
    LEVIATHAN = "Leviathan"
    BENAIAH = "Benaiah"
    SAMSON = "Samson"
    JEPHTHAH = "Jephthah"

class DroneWars:
    def __init__(self):
        self.orchestrator_model = "grok"
        self.drone_model = "deepseek"

    async def run(self, ark_data: Dict):
        """Main entry point - called automatically when Risk Curve updates"""
        active_captains = await self._run_orchestrator(ark_data)
        captain_tasks = [self._run_captain(c, ark_data) for c in active_captains]
        captain_results = await asyncio.gather(*captain_tasks)
        final_report = await self._run_jephthah_synthesis(ark_data, captain_results)
        return final_report

    async def _run_orchestrator(self, ark_data: Dict):
        """Decides which captains should participate"""
        prompt = get_orchestrator_prompt(ark_data)
        response = await call_grok_api(prompt)
        return response.get("selected_captains", ["Jephthah"])

    async def _run_captain(self, captain_name: str, ark_data: Dict):
        """Each captain can spawn drone teams"""
        prompt = get_captain_prompt(captain_name, ark_data)
        result = await call_grok_api(prompt)
        if result.get("needs_drones"):
            drone_results = await self._run_drone_team(result.get("drone_tasks", []))
            result = await self._give_drone_results_to_captain(captain_name, result, drone_results)
        return result

    async def _run_jephthah_synthesis(self, ark_data: Dict, captain_results: List):
        """Jephthah synthesizes everything"""
        prompt = get_captain_prompt("Jephthah", {"ark_data": ark_data, "captain_results": captain_results})
        return await call_grok_api(prompt)

    async def _run_drone_team(self, tasks):
        """Run cheap drones"""
        return await asyncio.gather(*[call_drone_api(t) for t in tasks])

    async def _give_drone_results_to_captain(self, captain_name: str, result, drone_results):
        """Feed back to captain"""
        return result
