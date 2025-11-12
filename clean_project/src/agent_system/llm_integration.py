"""
LLM integration for enhanced agent capabilities.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, cast

from .config_simple import get_api_key, settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        pass

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat completion."""
        pass

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """Optional: stream chat chunks as an async generator.
        Default implementation yields the full response once.
        """
        text = await self.chat(messages, **kwargs)

        async def _gen() -> AsyncIterator[str]:
            yield text

        return _gen()


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt using OpenAI."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key)

            response = await client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], **kwargs
            )

            return str(response.choices[0].message.content or "")

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return f"Error: {str(e)}"

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat completion using OpenAI."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key)

            response = await client.chat.completions.create(
                model=self.model, messages=messages, stream=False, **kwargs
            )

            return str(response.choices[0].message.content or "")

        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            return f"Error: {str(e)}"

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """Stream chat chunks using OpenAI if available, else fallback."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key)
            stream = await client.chat.completions.create(
                model=self.model, messages=messages, stream=True, **kwargs
            )

            async def _gen() -> AsyncIterator[str]:
                async for event in stream:
                    try:
                        delta = event.choices[0].delta.content or ""
                    except Exception:
                        delta = ""
                    if delta:
                        yield delta

            return _gen()
        except Exception as e:
            logger.warning(f"OpenAI streaming unavailable, falling back: {e}")
            return await super().stream_chat(messages, **kwargs)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt using Anthropic."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key)

            response = await client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )

            return str(response.content[0].text)

        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            return f"Error: {str(e)}"

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat completion using Anthropic."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key)

            response = await client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                messages=messages,
                stream=False,
                **kwargs,
            )

            return str(response.content[0].text)

        except Exception as e:
            logger.error(f"Anthropic chat failed: {e}")
            return f"Error: {str(e)}"

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            stream = await client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                messages=messages,
                stream=True,
                **kwargs,
            )

            async def _gen() -> AsyncIterator[str]:
                async for event in stream:
                    try:
                        # Depending on SDK, event may contain delta text
                        yield getattr(event, "delta", "") or ""
                    except Exception:
                        continue

            return _gen()
        except Exception as e:
            logger.warning(f"Anthropic streaming unavailable, falling back: {e}")
            return await super().stream_chat(messages, **kwargs)


class LocalProvider(LLMProvider):
    """Local LLM provider (generic). Use for non-Ollama local backends."""

    def __init__(self, base_url: str = "http://localhost:11434", model: Optional[str] = None):
        self.base_url = base_url
        self.model = model or settings.DEFAULT_LLM_MODEL

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using local LLM."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                response.raise_for_status()
                return str(response.json().get("response", ""))

        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            return f"Error: {str(e)}"

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat completion using local LLM."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                    timeout=30.0,
                )
                response.raise_for_status()
                return str(response.json().get("message", {}).get("content") or response.text)

        except Exception as e:
            logger.error(f"Local LLM chat failed: {e}")
            return f"Error: {str(e)}"

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """Attempt streaming with local LLM (Ollama-like), fallback to non-stream."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True},
                ) as resp:
                    resp.raise_for_status()

                    async def _gen() -> AsyncIterator[str]:
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            yield line

            return _gen()
        except Exception as e:
            logger.warning(f"Local LLM streaming unavailable, falling back: {e}")
            return await super().stream_chat(messages, **kwargs)


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider using OpenAI-compatible SDK with base_url override."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1", model: str = "openrouter/auto"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return str(response.choices[0].message.content or "")
        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            return f"Error: {str(e)}"

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                **kwargs,
            )
            return str(response.choices[0].message.content or "")
        except Exception as e:
            logger.error(f"OpenRouter chat failed: {e}")
            return f"Error: {str(e)}"

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs,
            )

            async def _gen() -> AsyncIterator[str]:
                async for event in stream:
                    try:
                        delta = event.choices[0].delta.content or ""
                    except Exception:
                        delta = ""
                    if delta:
                        yield delta

            return _gen()
        except Exception as e:
            logger.warning(f"OpenRouter streaming unavailable, falling back: {e}")
            return await super().stream_chat(messages, **kwargs)


class OllamaProvider(LLMProvider):
    """Explicit Ollama provider (local server)."""

    def __init__(self, base_url: str = "http://localhost:11434", model: Optional[str] = None):
        self.base_url = base_url
        self.model = model or settings.DEFAULT_LLM_MODEL

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return str(resp.json().get("response", ""))
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Error: {str(e)}"

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return str(resp.json().get("message", {}).get("content") or resp.text)
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            return f"Error: {str(e)}"

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True},
                ) as resp:
                    resp.raise_for_status()

                    async def _gen() -> AsyncIterator[str]:
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            yield line
            return _gen()
        except Exception as e:
            logger.warning(f"Ollama streaming unavailable, falling back: {e}")
            return await super().stream_chat(messages, **kwargs)


class LLMManager:
    """Manager for LLM providers with fallback support."""

    def __init__(self) -> None:
        self.providers: Dict[str, LLMProvider] = {}
        self.preferred_provider: Optional[str] = None
        self._initialize_providers()
        # Load preferred provider from config if available
        try:
            from .unified_config import unified_config as _cfg
            if _cfg.api.default_llm_provider:
                if _cfg.api.default_llm_provider in self.providers:
                    self.preferred_provider = _cfg.api.default_llm_provider
        except Exception:
            pass

    def _initialize_providers(self) -> None:
        """Initialize available LLM providers."""
        # Try OpenAI
        openai_key = get_api_key("openai")
        if openai_key:
            self.providers["openai"] = OpenAIProvider(openai_key)
            logger.info("OpenAI provider initialized")

        # Try Anthropic
        anthropic_key = get_api_key("anthropic")
        if anthropic_key:
            self.providers["anthropic"] = AnthropicProvider(anthropic_key)
            logger.info("Anthropic provider initialized")

        # Add OpenRouter if configured
        try:
            from .unified_config import unified_config as _cfg
        except Exception:
            _cfg = None
        openrouter_key = get_api_key("openrouter")
        if openrouter_key:
            try:
                self.providers["openrouter"] = OpenRouterProvider(
                    api_key=openrouter_key,
                    base_url=_cfg.api.openrouter_base_url if _cfg else "https://openrouter.ai/api/v1",
                )
                logger.info("OpenRouter provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter provider: {e}")

        # Add Ollama-specific provider if base URL present
        ollama_base = None
        ollama_model = None
        try:
            if _cfg:
                ollama_base = _cfg.api.ollama_base_url
                ollama_model = _cfg.api.ollama_model or _cfg.api.default_llm_model
        except Exception:
            pass
        if ollama_base:
            self.providers["ollama"] = OllamaProvider(base_url=ollama_base, model=ollama_model)
            logger.info("Ollama provider initialized")

        # Always add generic local provider as last fallback
        self.providers.setdefault("local", LocalProvider(base_url=ollama_base or "http://localhost:11434", model=ollama_model))
        logger.info("Local LLM provider initialized")

    async def generate(
        self, prompt: str, provider: Optional[str] = None, fallback: bool = True, **kwargs: Any
    ) -> str:
        """Generate text with optional fallback to other providers."""
        providers_to_try = []

        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            # Try preferred provider first, then others
            providers_to_try = []
            if self.preferred_provider and self.preferred_provider in self.providers:
                providers_to_try.append(self.preferred_provider)
            for name in self.providers.keys():
                if name not in providers_to_try:
                    providers_to_try.append(name)

        for provider_name in providers_to_try:
            try:
                provider_instance = self.providers[provider_name]
                result = await provider_instance.generate(prompt, **kwargs)

                if not result.startswith("Error:"):
                    logger.info(f"Successfully generated text using {provider_name}")
                    return result

            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue

        return "Error: All LLM providers failed"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        fallback: bool = True,
        **kwargs: Any,
    ) -> str:
        """Chat completion with optional fallback."""
        providers_to_try = []

        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            providers_to_try = []
            if self.preferred_provider and self.preferred_provider in self.providers:
                providers_to_try.append(self.preferred_provider)
            for name in self.providers.keys():
                if name not in providers_to_try:
                    providers_to_try.append(name)

        for provider_name in providers_to_try:
            try:
                provider_instance = self.providers[provider_name]
                result = await provider_instance.chat(messages, **kwargs)

                if not result.startswith("Error:"):
                    logger.info(f"Successfully completed chat using {provider_name}")
                    return result

            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue

        return "Error: All LLM providers failed"

    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self.providers.keys())

    def set_preferred_provider(self, name: Optional[str]) -> bool:
        """Set preferred provider (or None to clear). Returns True if applied."""
        if name is None:
            self.preferred_provider = None
            return True
        if name in self.providers:
            self.preferred_provider = name
            return True
        return False

    def get_preferred_provider(self) -> Optional[str]:
        return self.preferred_provider

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        fallback: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        providers_to_try: List[str] = []
        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            providers_to_try = list(self.providers.keys())
        for name in providers_to_try:
            try:
                gen = await self.providers[name].stream_chat(messages, **kwargs)
                return gen
            except Exception as e:
                logger.warning(f"Provider {name} stream failed: {e}")
                continue

        # Fallback: yield single full response
        async def _gen() -> AsyncIterator[str]:
            text = await self.chat(messages, provider=provider, fallback=fallback, **kwargs)
            yield text

        return _gen()

    def is_available(self, provider: str) -> bool:
        """Check if a provider is available."""
        return provider in self.providers


# Global LLM manager instance
llm_manager = LLMManager()


class LLMAugmentedActionSelector:
    """Action selector enhanced with LLM capabilities."""

    def __init__(self) -> None:
        self.llm_manager = llm_manager

    async def analyze_goal_context(self, goal_description: str, context: Dict[str, Any]) -> str:
        """Use LLM to analyze goal context and provide insights."""
        analysis_prompt = f"""
        Analyze this goal and context to provide strategic insights:
        
        Goal: {goal_description}
        Context: {json.dumps(context, indent=2)}
        
        Provide:
        1. Key challenges or considerations
        2. Suggested approach or methodology  
        3. Potential risks or obstacles
        4. Success criteria to measure progress
        
        Be concise and actionable.
        """

        result = await self.llm_manager.generate(analysis_prompt, max_tokens=500, temperature=0.3)

        return result

    async def suggest_actions(
        self, goal_description: str, available_actions: List[str]
    ) -> List[Dict[str, Any]]:
        """Use LLM to suggest optimal action sequences."""
        suggestions_prompt = f"""
        Given this goal and available actions, suggest the best approach:
        
        Goal: {goal_description}
        Available Actions: {', '.join(available_actions)}
        
        For each suggested action, provide:
        - Action name
        - Reasoning for inclusion
        - Expected outcome
        - Priority (1-10)
        
        Return as JSON array.
        """

        result = await self.llm_manager.generate(
            suggestions_prompt, max_tokens=800, temperature=0.4
        )

        try:
            # Try to parse as JSON
            suggestions = cast(List[Dict[str, Any]], json.loads(result))
            return suggestions
        except json.JSONDecodeError:
            # Fallback to text parsing
            return [
                {
                    "action": "analyze_goal",
                    "reasoning": result,
                    "expected_outcome": "insights",
                    "priority": 5,
                }
            ]

    async def evaluate_action_outcome(
        self, action_description: str, outcome: Dict[str, Any], goal: str
    ) -> Dict[str, Any]:
        """Use LLM to evaluate action outcomes and provide feedback."""
        evaluation_prompt = f"""
        Evaluate this action outcome for strategic feedback:
        
        Action: {action_description}
        Goal: {goal}
        Outcome: {json.dumps(outcome, indent=2)}
        
        Provide:
        1. Success assessment (rate 1-10)
        2. Key learnings
        3. Next steps recommendations
        4. Any concerns or red flags
        
        Be objective and constructive.
        """

        result = await self.llm_manager.generate(evaluation_prompt, max_tokens=600, temperature=0.2)

        return {"evaluation": result, "llm_insights": True}
