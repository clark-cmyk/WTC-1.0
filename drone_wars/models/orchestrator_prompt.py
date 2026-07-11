def get_orchestrator_prompt(ark_data: Dict):
    return f"""Orchestrator. Risk Curve data: {ark_data}. Decide which captains to activate (Abaddon, Goliath, Leviathan, Benaiah, Samson, Jephthah). Output: selected_captains list."""
