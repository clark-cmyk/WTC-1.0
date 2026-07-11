def get_captain_prompt(captain: str, ark_data: Dict):
    prompts = {
        "Abaddon": f"Abaddon - Destruction Analyst. Analyze high-beta weakness. Data: {ark_data}. Output: risk signals.",
        "Goliath": f"Goliath - Giant Slayer. Focus on equity depth. Data: {ark_data}. Output: breadth commentary.",
        "Leviathan": f"Leviathan - Sea Monster. Liquidity + credit. Data: {ark_data}. Output: macro stress.",
        "Benaiah": f"Benaiah - Lion Slayer. Bitcoin Basis. Data: {ark_data}. Output: crypto basis.",
        "Samson": f"Samson - Strength. High Beta. Data: {ark_data}. Output: beta performance.",
        "Jephthah": f"Jephthah - Synthesizer. Combine all captains. Data: {ark_data}. Output: final report."
    }
    return prompts.get(captain, "Generic captain.")