from typing import Dict, List, Any
import asyncio
import os
from grok import GrokAPI
from deepseek import DeepSeekAPI

class LLMClient:
    def __init__(self):
        self.grok = GrokAPI(api_key=os.getenv("GROK_API_KEY"))
        self.deepseek = DeepSeekAPI(api_key=os.getenv("DEEPSEEK_API_KEY"))

    async def call_captain(self, captain_name: str, system_prompt: str, user_message: str) -> Dict:
        """Used for the 6 main captains (runs on Grok)"""
        full_prompt = f"You are {captain_name}.\n{system_prompt}"
        response = await self.grok.chat.completions.create(
            model="grok-beta",
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3
        )
        return response

    async def call_drone(self, task: str) -> Dict:
        """Used for cheap open-source drones"""
        response = await self.deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": task}],
            temperature=0.1
        )
        return response
