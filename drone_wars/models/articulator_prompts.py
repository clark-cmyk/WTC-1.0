def get_articulator_prompt(node: str, report: Dict):
    prompts = {
        "liquidity": f"Articulate Liquidity node. Report: {report}. Output: human commentary with math.",
        "credit": f"Articulate Credit node. Report: {report}. Output: human commentary with math.",
        "equityDepth": f"Articulate Equity Depth node. Report: {report}. Output: human commentary with math.",
        "highBeta": f"Articulate High Beta node. Report: {report}. Output: human commentary with math.",
        "bitcoinBasis": f"Articulate Bitcoin Basis node. Report: {report}. Output: human commentary with math."
    }
    return prompts.get(node, "Generic articulation.")
