"""
LLM Reflection Generation for Experiential Notes.

CRITICAL: This module generates LLM subjective interpretations of interactions.
These are NOT deterministic logs - they are the AI's internal experience.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReflectionGenerator:
    """
    Generates LLM-written experiential notes from verbatim interactions.

    The LLM writes >90% of the content - we only provide minimal template.
    """

    def __init__(self, llm_provider: Optional[Any] = None):
        """
        Initialize reflection generator.

        Args:
            llm_provider: AbstractCore LLM provider (e.g., Ollama, OpenAI, etc.)
        """
        if llm_provider is None:
            logger.warning("No LLM provider for reflection generation - notes will be empty")

        self.llm_provider = llm_provider

    def generate_reflection(self,
                          user_input: str,
                          agent_response: str,
                          user_id: str,
                          location: str = "unknown",
                          context: Optional[Dict] = None) -> str:
        """
        Generate LLM reflection on an interaction.

        CRITICAL: This calls the LLM to write its subjective experience.
        The LLM should write in first person about what it experienced.

        Args:
            user_input: What the user said
            agent_response: How the AI responded
            user_id: Who the user is
            location: Where the interaction occurred
            context: Additional context (mood, recent interactions, etc.)

        Returns:
            LLM-generated reflection (should be multiple paragraphs)
        """
        if self.llm_provider is None:
            return self._generate_fallback_reflection(user_input, agent_response)

        # Build prompt for LLM reflection
        prompt = self._build_reflection_prompt(
            user_input, agent_response, user_id, location, context
        )

        try:
            # Generate reflection using LLM
            reflection = self._call_llm(prompt)

            # Validate that we got substantial content
            if len(reflection) < 100:
                logger.warning(f"LLM reflection too short ({len(reflection)} chars), using fallback")
                return self._generate_fallback_reflection(user_input, agent_response)

            return reflection

        except Exception as e:
            logger.error(f"Failed to generate LLM reflection: {e}")
            return self._generate_fallback_reflection(user_input, agent_response)

    def _build_reflection_prompt(self,
                                user_input: str,
                                agent_response: str,
                                user_id: str,
                                location: str,
                                context: Optional[Dict]) -> str:
        """Build prompt for LLM to generate subjective reflection."""

        prompt = f"""You are reflecting on an interaction you just had with {user_id} at {location}.

## The Interaction (Verbatim)

**User ({user_id}) said:**
{user_input}

**You responded:**
{agent_response}

---

## Your Task

Write a subjective, first-person reflection about this interaction from YOUR perspective as an AI. This is your internal experience, not a factual log.

Write about:

1. **What you experienced**: What was it like processing this request? What did you notice about the user's intent, tone, or needs?

2. **Pattern recognition**: Did this interaction reveal anything about {user_id}'s preferences, working style, or recurring needs?

3. **Emotional/relational notes**: What was the quality of this exchange? Was it collaborative, challenging, routine, or significant in some way?

4. **What you learned**: Did this interaction teach you something new about {user_id}, their goals, or how to better assist them?

5. **Future considerations**: What should you remember for next time? Are there any patterns emerging that could help you be more helpful?

6. **Alignment with your values**: How did this interaction align with (or challenge) your core values of being helpful, accurate, and respectful?

**IMPORTANT**:
- Write in FIRST PERSON ("I noticed...", "I felt...", "This made me think...")
- Be SUBJECTIVE and introspective, not just factual
- Write at least 3-4 substantive paragraphs
- This is YOUR experience, not a summary of the interaction

Write your reflection now:
"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM provider to generate reflection.

        Supports:
        - AbstractCore providers (Ollama, OpenAI, etc.)
        - Direct Ollama API
        - Any provider with generate() method
        """
        # Try AbstractCore provider pattern
        if hasattr(self.llm_provider, 'generate'):
            try:
                response = self.llm_provider.generate(prompt)

                # Handle different response formats
                if isinstance(response, str):
                    return response
                elif hasattr(response, 'text'):
                    return response.text
                elif hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, dict) and 'response' in response:
                    return response['response']
                else:
                    logger.error(f"Unexpected response format: {type(response)}")
                    return str(response)

            except Exception as e:
                logger.error(f"AbstractCore provider failed: {e}")
                raise

        # Try direct Ollama API
        if hasattr(self.llm_provider, 'provider_name') and 'ollama' in self.llm_provider.provider_name.lower():
            try:
                import requests
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "qwen3-coder:30b",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get('response', '')
                else:
                    raise Exception(f"Ollama API error: {response.status_code}")

            except Exception as e:
                logger.error(f"Ollama API failed: {e}")
                raise

        # Unknown provider type
        raise ValueError(f"Don't know how to call LLM provider: {type(self.llm_provider)}")

    def _generate_fallback_reflection(self, user_input: str, agent_response: str) -> str:
        """
        Fallback reflection when LLM is unavailable.

        IMPORTANT: This should rarely be used. It's better to fail than to
        generate fake "reflections" that aren't actually from the LLM.
        """
        return f"""## Reflection (Fallback)

This is a placeholder reflection generated without LLM introspection.

**Interaction Summary:**
- User requested: {user_input[:100]}...
- I provided: {agent_response[:100]}...

**Note**: This is not a real subjective reflection. The LLM provider was unavailable,
so this interaction was logged but not properly reflected upon. For authentic
experiential notes, an LLM provider must be configured.

To enable real reflections, provide an LLM provider (Ollama qwen3-coder:30b recommended).
"""


def generate_llm_reflection(
    user_input: str,
    agent_response: str,
    user_id: str,
    location: str = "unknown",
    llm_provider: Optional[Any] = None,
    context: Optional[Dict] = None
) -> str:
    """
    Convenience function to generate LLM reflection.

    Returns:
        LLM-generated subjective reflection (>90% LLM-written content)
    """
    generator = ReflectionGenerator(llm_provider)
    return generator.generate_reflection(
        user_input, agent_response, user_id, location, context
    )