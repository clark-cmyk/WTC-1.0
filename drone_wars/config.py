from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class LordConfig:
    name: str
    title: str
    description: str

@dataclass
class RetainerConfig:
    name: str
    description: str
    capabilities: List = field(default_factory=list)

@dataclass
class DroneWarsConfig:
    sovereign_name: str = "Sovereign"
    sovereign_model: str = "grok"
    
    lords: List = field(default_factory=lambda: [
        LordConfig(name="Abaddon", title="Destruction Analyst", description="Identifies weakness and risk in high-beta assets"),
        LordConfig(name="Goliath", title="Giant Slayer", description="Analyzes equity depth and market breadth"),
        LordConfig(name="Leviathan", title="Sea Monster", description="Monitors liquidity and credit market stress"),
        LordConfig(name="Benaiah", title="Lion Slayer", description="Specialist in Bitcoin Basis trading"),
        LordConfig(name="Samson", title="Strength", description="Analyzes high-beta performance"),
        LordConfig(name="Jephthah", title="Synthesizer", description="Combines all analysis into final coherent report")
    ])
    
    retainers: List = field(default_factory=lambda: [
        RetainerConfig(name="Data Retainer", description="Fetches fresh market data from external sources", capabilities=["data_collection"]),
        RetainerConfig(name="Calculation Retainer", description="Performs mathematical calculations", capabilities=["calculations"]),
        RetainerConfig(name="Analysis Retainer", description="Runs statistical analysis", capabilities=["statistics"])
    ])
    
    tools: Dict = field(default_factory=lambda: {
        "collect_data": "/api/collect-data"
    })

config = DroneWarsConfig()
