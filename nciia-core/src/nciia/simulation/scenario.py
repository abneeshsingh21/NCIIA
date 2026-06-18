
import asyncio
import random
import uuid
from datetime import datetime
from typing import List, Dict, Any

from nciia.models import Signal, Persona, ThreatScore
from nciia.utils import get_logger

logger = get_logger(__name__)

class ScenarioGenerator:
    """
    Generates coherent, realistic threat scenarios (Kill Chains)
    to drive the N-CIIA platform with "smart" looking data.
    """
    
    SCENARIOS = {
        "APT_DEEP_RUN": {
            "name": "Operation Deep Run",
            "actor": "APT-29 (Cozy Bear) Imitator",
            "stages": [
                {
                    "type": "recon",
                    "source": "pastebin",
                    "content": "Subject target list leaked: ceo@target-corp.com, cfo@target-corp.com",
                    "confidence": 0.85
                },
                {
                    "type": "weaponization",
                    "source": "virustotal",
                    "content": "New macro-enabled Excel doc detected with hash matching 'DeepRun' signature.",
                    "confidence": 0.92
                },
                {
                    "type": "delivery",
                    "source": "email_gateway",
                    "content": "Suspicious email wave detected from domain 'secure-micros0ft-update.com'.",
                    "confidence": 0.78
                },
                {
                    "type": "c2",
                    "source": "network_traffic",
                    "content": "Beacon detected to IP 185.20.10.5 (Known C2 Node). Pulse interval: 60s.",
                    "confidence": 0.99
                }
            ]
        },
        "DARK_MARKET_LEAK": {
            "name": "Credential Burst #992",
            "actor": "Broker_X",
            "stages": [
                {
                    "type": "darkweb_monitor",
                    "source": "raidforums_mirror",
                    "content": "New database listing: 'Gov_Access_2025.sql'. Price: 2 BTC.",
                    "confidence": 0.95
                },
                {
                    "type": "social_media",
                    "source": "twitter",
                    "content": "Threat actor 'Broker_X' claims responsibility for new gov leak.",
                    "confidence": 0.60
                }
            ]
        }
    }

    def __init__(self):
        self.active_campaigns = []
        self._running = False

    async def start_simulation(self, queue: asyncio.Queue):
        """Starts injecting intelligent scenarios into the system."""
        self._running = True
        logger.info("simulation_started", mode="realistic_kill_chain")
        
        while self._running:
            # Pick a scenario
            key = random.choice(list(self.SCENARIOS.keys()))
            scenario = self.SCENARIOS[key]
            
            # Start Campaign
            campaign_id = datetime.now().strftime("%Y%m%d") + "-" + key
            logger.info("campaign_initiated", campaign=scenario["name"])
            
            for stage in scenario["stages"]:
                if not self._running: break
                
                # Emit Signal
                signal = Signal(
                    id=uuid.uuid4(),
                    content=stage["content"],
                    source_type=stage["source"],
                    discovered_at=datetime.now(),
                    metadata={
                        "campaign": campaign_id,
                        "actor": scenario["actor"],
                        "stage": stage["type"],
                        "simulated": True
                    }
                )
                
                # Push to queue (simulating ingestion)
                await queue.put(signal)
                logger.info("signal_injected", stage=stage["type"], actor=scenario["actor"])
                
                # Variable delay to feel "live"
                delay = random.uniform(2.0, 5.0)
                await asyncio.sleep(delay)
            
            # Pause between campaigns
            await asyncio.sleep(random.uniform(5.0, 10.0))

    def stop(self):
        self._running = False
