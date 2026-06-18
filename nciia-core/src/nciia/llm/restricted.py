"""
Restricted LLM Integration

Provides controlled LLM access for reasoning and explanation.
LLM operates ONLY on verified system outputs - never invents data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OLLAMA = "ollama"
    NONE = "none"


@dataclass
class LLMConfig:
    """LLM configuration."""
    
    provider: LLMProvider = LLMProvider.NONE
    model: str = ""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.3  # Low for factual responses


@dataclass
class LLMResponse:
    """Response from LLM."""
    
    content: str
    model: str
    tokens_used: int
    latency_ms: float
    timestamp: datetime


class RestrictedLLM:
    """
    Restricted LLM for reasoning over verified outputs.
    
    CRITICAL: LLM can ONLY:
    - Explain existing findings
    - Summarize verified data
    - Answer questions about system outputs
    
    LLM CANNOT:
    - Make up entities or signals
    - Invent threat indicators
    - Generate unverified intelligence
    """
    
    SYSTEM_PROMPT = """You are an AI assistant for the N-CIIA cyber intelligence platform.

CRITICAL RESTRICTIONS:
1. You may ONLY reason about data provided in the context
2. You CANNOT make up entities, signals, or threat indicators
3. All your outputs must reference verified system data
4. When uncertain, explicitly state "insufficient data"
5. Always explain your reasoning transparently

Your role is to help analysts understand findings, not generate new intelligence."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize LLM client based on provider."""
        if self.config.provider == LLMProvider.NONE:
            logger.info("llm_disabled", reason="No provider configured")
            return False
        
        try:
            if self.config.provider == LLMProvider.OPENAI:
                await self._init_openai()
            elif self.config.provider == LLMProvider.ANTHROPIC:
                await self._init_anthropic()
            elif self.config.provider == LLMProvider.GROQ:
                await self._init_groq()
            elif self.config.provider == LLMProvider.OLLAMA:
                await self._init_ollama()
            
            self._initialized = True
            logger.info("llm_initialized", provider=self.config.provider.value)
            return True
            
        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            return False
    
    async def _init_openai(self) -> None:
        """Initialize OpenAI client."""
        # Would use openai library in production
        pass
    
    async def _init_anthropic(self) -> None:
        """Initialize Anthropic client."""
        # Would use anthropic library in production
        pass
    
    async def _init_groq(self) -> None:
        """Initialize Groq client."""
        import httpx
        self._client = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # Set default model if not specified
        if not self.config.model:
            self.config.model = "llama-3.1-8b-instant"
        logger.info("groq_initialized", model=self.config.model)
    
    async def _init_ollama(self) -> None:
        """Initialize Ollama (local) client."""
        # Would use httpx for local Ollama API
        pass
    
    async def explain(
        self,
        finding_type: str,
        finding_data: dict[str, Any],
        question: Optional[str] = None,
    ) -> LLMResponse:
        """
        Get LLM explanation for a finding.
        
        Args:
            finding_type: Type of finding (threat_score, persona, etc.)
            finding_data: The verified finding data
            question: Optional specific question
            
        Returns:
            LLMResponse with explanation
        """
        if not self._initialized:
            return self._fallback_explanation(finding_type, finding_data)
        
        # Build prompt with only verified data
        prompt = self._build_explanation_prompt(finding_type, finding_data, question)
        
        try:
            response = await self._call_llm(prompt)
            return response
        except Exception as e:
            logger.error("llm_explain_failed", error=str(e))
            return self._fallback_explanation(finding_type, finding_data)
    
    async def summarize(
        self,
        data: dict[str, Any],
        context: str = "",
    ) -> LLMResponse:
        """
        Summarize verified data.
        
        Args:
            data: Verified data to summarize
            context: Additional context
            
        Returns:
            LLMResponse with summary
        """
        if not self._initialized:
            return self._fallback_summary(data)
        
        prompt = f"""Summarize the following verified intelligence data.
Context: {context}

Data:
{self._format_data(data)}

Provide a concise, factual summary. Do not add information not present in the data."""

        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error("llm_summarize_failed", error=str(e))
            return self._fallback_summary(data)
    
    async def answer_question(
        self,
        question: str,
        context_data: dict[str, Any],
    ) -> LLMResponse:
        """
        Answer a question about verified data.
        
        Args:
            question: Analyst question
            context_data: Relevant verified data
            
        Returns:
            LLMResponse with answer
        """
        if not self._initialized:
            return LLMResponse(
                content="LLM not configured. Cannot answer questions.",
                model="none",
                tokens_used=0,
                latency_ms=0,
                timestamp=datetime.utcnow(),
            )
        
        prompt = f"""Answer the following question based ONLY on the provided data.
If the answer cannot be determined from the data, say "insufficient data."

Question: {question}

Available Data:
{self._format_data(context_data)}

Answer:"""

        return await self._call_llm(prompt)
    
    async def _call_llm(self, prompt: str) -> LLMResponse:
        """Call the LLM API."""
        start = datetime.utcnow()
        
        # Use Groq API if configured
        if self.config.provider == LLMProvider.GROQ and self._client:
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json={
                        "model": self.config.model,
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    tokens_used=tokens,
                    latency_ms=latency,
                    timestamp=datetime.utcnow(),
                )
            except Exception as e:
                logger.error("groq_api_error", error=str(e))
                raise
        
        # Fallback for unconfigured providers
        response_text = "[LLM not fully configured] Based on the provided data..."
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        
        return LLMResponse(
            content=response_text,
            model=self.config.model or "fallback",
            tokens_used=0,
            latency_ms=latency,
            timestamp=datetime.utcnow(),
        )
    
    def _build_explanation_prompt(
        self,
        finding_type: str,
        data: dict[str, Any],
        question: Optional[str],
    ) -> str:
        """Build explanation prompt."""
        prompt = f"""Explain the following {finding_type} finding.

Finding Data:
{self._format_data(data)}

"""
        if question:
            prompt += f"Specific Question: {question}\n\n"
        
        prompt += "Provide a clear, factual explanation based only on the data above."
        return prompt
    
    def _format_data(self, data: dict[str, Any]) -> str:
        """Format data for prompt inclusion."""
        lines = []
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                lines.append(f"- {key}: {value}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _fallback_explanation(
        self,
        finding_type: str,
        data: dict[str, Any],
    ) -> LLMResponse:
        """Generate fallback explanation without LLM."""
        content = f"[Automated Explanation]\n\nFinding Type: {finding_type}\n\n"
        
        for key, value in data.items():
            content += f"• {key.replace('_', ' ').title()}: {value}\n"
        
        return LLMResponse(
            content=content,
            model="fallback",
            tokens_used=0,
            latency_ms=0,
            timestamp=datetime.utcnow(),
        )
    
    def _fallback_summary(self, data: dict[str, Any]) -> LLMResponse:
        """Generate fallback summary without LLM."""
        content = "[Automated Summary]\n\n"
        content += f"Data contains {len(data)} fields.\n"
        
        for key in list(data.keys())[:5]:
            content += f"• {key.replace('_', ' ').title()}\n"
        
        return LLMResponse(
            content=content,
            model="fallback",
            tokens_used=0,
            latency_ms=0,
            timestamp=datetime.utcnow(),
        )


# Global LLM instance
_llm: Optional[RestrictedLLM] = None


async def get_llm() -> RestrictedLLM:
    """Get or create restricted LLM."""
    global _llm
    if _llm is None:
        _llm = RestrictedLLM()
        await _llm.initialize()
    return _llm
