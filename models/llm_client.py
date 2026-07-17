from typing import Dict, Any
import os
import httpx
import json
import re

class LLMClient:
    def __init__(self):
        self.grok_api_key = os.getenv("GROK_API_KEY")
        self.base_url = "https://api.x.ai/v1"
        # Use GROK_MODEL env var or default to fast agentic model
        self.default_model = os.getenv("GROK_MODEL", "grok-build-0.1")

    async def call(self, prompt: str, model: str = None) -> Dict[str, Any]:
        model = model or self.default_model
        try:
            headers = {
                "Authorization": f"Bearer {self.grok_api_key}",
                "Content-Type": "application/json"
            }

            full_prompt = prompt + """

Respond with ONLY valid JSON. No explanations. No markdown. No extra text.
"""

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": full_prompt}],
                "temperature": 0.0
            }

            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(json)?", "", content, flags=re.IGNORECASE).strip()
                    content = content.rstrip("```").strip()

                try:
                    return json.loads(content)
                except:
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(0))
                        except:
                            pass
                    return {"raw_response": content, "parse_failed": True}

        except Exception as e:
            print(f"LLMClient error: {str(e)}")
            return {"error": str(e)}
