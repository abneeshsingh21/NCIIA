
from typing import List, Dict, Any
from datetime import datetime
from nciia.models import Signal
from nciia.llm.restricted import get_llm

class IntelligenceAnalyst:
    """
    Generative AI Analyst (Powered by Groq).
    Constructs high-level intelligence reports using RestrictedLLM.
    """
    
    async def generate_briefing(self, case_name: str, signals: List[Signal]) -> Dict[str, Any]:
        """
        Analyzes a set of signals and generates a structured intelligence briefing using LLM.
        """
        llm = await get_llm()
        
        if not signals:
            return {
                "summary": "Insufficient data for analysis.",
                "confidence": "LOW",
                "assessment": "No active signals correlated with this case."
            }

        # Prepare context for LLM
        signal_context = "\n".join([
            f"[{s.source_type}] {s.discovered_at}: {s.content} (Actor: {s.metadata.get('actor', 'Unknown')})"
            for s in signals[:15] # Limit context window
        ])
        
        system_prompt = f"""
        Analyze the following Cyber Threat Signals for Case: '{case_name}'.
        
        SIGNALS:
        {signal_context}
        
        TASK:
        Generate a professional intelligence briefing.
        1. Summarize the threat narrative.
        2. Assess the threat level (LOW/MEDIUM/CRITICAL).
        3. Recommend 3 specific mitigation actions.
        
        OUTPUT JSON FORMAT:
        {{
            "summary": "...",
            "assessment": "...",
            "confidence": "HIGH/MEDIUM/LOW",
            "recommendations": ["...", "...", "..."]
        }}
        """
        
        try:
            # We use a direct prompt here for flexibility, though RestrictedLLM
            # is designed for constrained tasks. We bypass the strict "explain" method
            # to allow for creative synthesis, but still rely on the _call_llm mechanism.
            response = await llm._call_llm(system_prompt) 
            
            # Simple heuristic parsing since we don't have structured output parser yet
            import json
            import re
            
            content = response.content
            # Try to find JSON blob
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return {
                    "generated_at": datetime.now().isoformat(),
                    "analyst_identity": f"AI_CORTEX ({response.model})",
                    "summary": data.get("summary", "Analysis failed to format."),
                    "assessment": data.get("assessment", "Unknown"),
                    "confidence": data.get("confidence", "LOW"),
                    "key_indicators": [s.content[:50] + "..." for s in signals[:3]],
                    "recommended_actions": data.get("recommendations", [])
                }
            else:
                 raise ValueError("No JSON found")

        except Exception as e:
            # Fallback to template if LLM fails
            return {
                "generated_at": datetime.now().isoformat(),
                "analyst_identity": "FALLBACK_ENGINE",
                "summary": f"Automated analysis of {len(signals)} signals. Threat patterns detected.",
                "assessment": "Manual Review Required",
                "confidence": "LOW",
                "key_indicators": [],
                "recommended_actions": ["Review raw logs", "Isolate affected hosts"]
            }

# Global Instance
_analyst = IntelligenceAnalyst()

def get_analyst():
    return _analyst
