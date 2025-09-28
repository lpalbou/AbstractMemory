#!/usr/bin/env python3
"""
ReAct Loop Module - Standalone implementation of ReAct reasoning

Based on the working implementation from nexus.py, this module provides
a clean, reusable ReAct loop that can be integrated into any UI.

Key features:
- Proper context accumulation (append, don't replace)
- Robust action parsing (multiple formats)
- Real tool execution
- Configurable callbacks for UI updates
"""

import re
import json
import time
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Callable, Tuple, List
from dataclasses import dataclass


@dataclass
class ReactConfig:
    """Configuration for ReAct reasoning loop."""
    max_iterations: int = 25
    observation_display_limit: int = 500
    include_memory: bool = True
    context_tokens_limit: int = 2000


class ReactLoop:
    """
    Standalone ReAct reasoning loop implementation.

    This class handles the iterative reasoning process where an LLM
    alternates between thinking and acting using tools until it
    reaches a final answer.
    """

    def __init__(self, session, config: Optional[ReactConfig] = None):
        """
        Initialize the ReAct loop.

        Args:
            session: MemorySession with LLM and tools
            config: Optional configuration for the loop
        """
        self.session = session
        self.config = config or ReactConfig()

        # Tracking for debugging/analysis
        self.last_context = ""
        self.last_reasoning_log = []
        self.last_total_time = 0.0

    def parse_action_from_response(self, response: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parse action from LLM response. Returns (tool_name, tool_input) or None.

        Handles multiple formats:
        1. <|tool_call|> format (modern)
        2. Action: / Action Input: format (traditional ReAct)
        """
        # First try to parse <|tool_call|> format (modern format)
        tool_call_pattern = r'<\|tool_call\|>\s*\n?\s*\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\s*\}'
        tool_call_match = re.search(tool_call_pattern, response, re.DOTALL)

        if tool_call_match:
            try:
                tool_name = tool_call_match.group(1)
                arguments_str = tool_call_match.group(2)
                tool_input = json.loads(arguments_str)
                return tool_name, tool_input
            except json.JSONDecodeError:
                pass

        # Also try alternative <|tool_call|> format
        alt_tool_pattern = r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\s*\}'
        alt_match = re.search(alt_tool_pattern, response, re.DOTALL)

        if alt_match:
            try:
                tool_name = alt_match.group(1)
                arguments_str = alt_match.group(2)
                tool_input = json.loads(arguments_str)
                return tool_name, tool_input
            except json.JSONDecodeError:
                pass

        # Fall back to traditional Action: pattern
        action_pattern = r'Action:\s*(\w+)'
        action_match = re.search(action_pattern, response, re.IGNORECASE)

        if not action_match:
            return None

        tool_name = action_match.group(1)

        # Look for Action Input: pattern
        input_pattern = r'Action Input:\s*({.*?})'
        input_match = re.search(input_pattern, response, re.DOTALL)

        if input_match:
            try:
                tool_input = json.loads(input_match.group(1))
                return tool_name, tool_input
            except json.JSONDecodeError:
                # Try to extract simple string input
                simple_pattern = r'Action Input:\s*"([^"]+)"'
                simple_match = re.search(simple_pattern, response)
                if simple_match:
                    return tool_name, {"input": simple_match.group(1)}

        # No valid input found
        return tool_name, {}

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool by name with given input.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of parameters for the tool

        Returns:
            String result from tool execution or error message
        """
        try:
            # Get tools from session
            tools = getattr(self.session, 'tools', [])
            if not tools:
                return "Error: No tools available"

            # Find the tool by name
            target_tool = None
            for tool in tools:
                if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                    target_tool = tool
                    break

            if not target_tool:
                available_tools = [getattr(t, '__name__', 'unknown') for t in tools]
                return f"Error: Tool '{tool_name}' not found. Available tools are: {', '.join(available_tools)}. Please use one of these tool names in your Action."

            # Execute the tool with the input
            if isinstance(tool_input, dict):
                result = target_tool(**tool_input)
            else:
                result = target_tool(tool_input)

            return str(result)

        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    async def process_query(
        self,
        user_input: str,
        callbacks: Optional[Dict[str, Callable]] = None
    ) -> str:
        """
        Process a user query through the ReAct loop.

        Args:
            user_input: The user's question/request
            callbacks: Optional dict of callback functions for UI updates:
                - on_iteration(iteration, max_iterations): Called at start of each iteration
                - on_response(response): Called after LLM generates response
                - on_action(tool_name, tool_input): Called when tool is about to execute
                - on_observation(tool_result): Called after tool execution
                - on_final_answer(answer): Called when final answer is reached

        Returns:
            Final answer from the ReAct reasoning process
        """
        callbacks = callbacks or {}

        # Build initial context with user question
        # CRITICAL: This context accumulates through iterations
        context = f"Question: {user_input}\n"

        # Track reasoning for debugging
        reasoning_log = []
        start_time = time.time()

        try:
            for iteration in range(self.config.max_iterations):
                iter_start = time.time()

                # Notify UI of iteration start
                if 'on_iteration' in callbacks:
                    callbacks['on_iteration'](iteration + 1, self.config.max_iterations)

                # Generate response using accumulated context
                # This is where the magic happens - we use ALL previous context
                loop = asyncio.get_event_loop()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    response = await loop.run_in_executor(
                        executor,
                        lambda: self.session.generate(
                            context,  # CRITICAL: Use accumulated context
                            user_id="react_user",
                            include_memory=self.config.include_memory
                        )
                    )

                # Extract response content
                if hasattr(response, 'content'):
                    agent_response = response.content.strip()
                else:
                    agent_response = str(response).strip()

                iter_time = time.time() - iter_start

                # Log this iteration
                reasoning_log.append({
                    'iteration': iteration + 1,
                    'response': agent_response,
                    'timestamp': time.time(),
                    'generation_time': iter_time
                })

                # Notify UI of response
                if 'on_response' in callbacks:
                    callbacks['on_response'](agent_response)

                # Check if this is a Final Answer
                if "Final Answer:" in agent_response:
                    parts = agent_response.split("Final Answer:", 1)
                    if len(parts) > 1:
                        final_answer = parts[1].strip()

                        # Store debugging info
                        self.last_context = context
                        self.last_reasoning_log = reasoning_log
                        self.last_total_time = time.time() - start_time

                        # Notify UI of final answer
                        if 'on_final_answer' in callbacks:
                            callbacks['on_final_answer'](final_answer)

                        return final_answer

                # Parse for Action
                action_match = self.parse_action_from_response(agent_response)
                if action_match:
                    tool_name, tool_input = action_match

                    # Notify UI of tool execution
                    if 'on_action' in callbacks:
                        callbacks['on_action'](tool_name, tool_input)

                    # Execute the tool
                    tool_result = self.execute_tool(tool_name, tool_input)

                    # Notify UI of observation
                    if 'on_observation' in callbacks:
                        callbacks['on_observation'](tool_result)

                    # CRITICAL: Build up ReAct scratchpad (append, don't replace)
                    full_observation = f"Observation: {tool_result}"
                    context += agent_response + "\n" + full_observation + "\n"

                    # Log tool execution
                    reasoning_log[-1]['tool_execution'] = {
                        'tool_name': tool_name,
                        'tool_input': tool_input,
                        'tool_result': tool_result,
                        'execution_time': time.time() - iter_start
                    }

                else:
                    # No action found - just thinking
                    # CRITICAL: Still add to context for next iteration
                    context += agent_response + "\n"

                    # Check for completion without "Final Answer:" format
                    # BUT don't exit if response contains tool calls (still in reasoning)
                    if ("Thought:" not in agent_response and "Action:" not in agent_response and
                        "<|tool_call|>" not in agent_response and "tool_call" not in agent_response):
                        if len(agent_response) > 50:  # Substantial response without tool calls
                            # Store debugging info
                            self.last_context = context
                            self.last_reasoning_log = reasoning_log
                            self.last_total_time = time.time() - start_time

                            # Notify UI of final answer
                            if 'on_final_answer' in callbacks:
                                callbacks['on_final_answer'](agent_response)

                            return agent_response

            # Max iterations reached
            self.last_context = context
            self.last_reasoning_log = reasoning_log
            self.last_total_time = time.time() - start_time

            return "I apologize, I couldn't complete the reasoning within the allowed iterations. Please try rephrasing your question or ask for a simpler task."

        except Exception as e:
            # Store debugging info even on error
            self.last_context = context
            self.last_reasoning_log = reasoning_log
            self.last_total_time = time.time() - start_time

            return f"Error in ReAct reasoning: {e}"

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debugging information from the last run."""
        return {
            'last_context': self.last_context,
            'reasoning_log': self.last_reasoning_log,
            'total_time': self.last_total_time,
            'iterations': len(self.last_reasoning_log),
            'context_length': len(self.last_context),
            'estimated_tokens': self._estimate_tokens(self.last_context)
        }