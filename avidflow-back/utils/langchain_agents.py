"""
LangChain-compatible Agent implementations.

Wraps our existing agent loop logic as a LangChain Runnable, enabling
LCEL composition while maintaining full backward compatibility.

TOKEN BUDGET MANAGEMENT (gpt-4o-mini: 128K context limit):
=============================================================
Fixed overhead (always present):
- System prompt: 7-10K tokens (Persian tax law assistant prompt)
- Tool schemas: 10-15K tokens (3 Qdrant retriever tools with descriptions)
- Message formatting: 3-5K tokens (role markers, JSON structure)
Total fixed: ~25-30K tokens

Dynamic content (varies per query):
- Tool results: Up to 25K tokens per tool (topK=20+12+8, scoreThreshold filters to ~15 docs)
- Memory history: 5-15K tokens (5-message window with previous Q&A pairs)
- User query: 0.1-1K tokens (typically short questions)
- Model completion: Up to 16K tokens (max_tokens=16000)

Safe limits:
- max_total_tokens: 95K (leaves 30K buffer for overhead + completion)
- max_tool_result_tokens: 25K per tool (prevents single tool from dominating)
- Multi-iteration threshold: 50K on iteration 2+ (prevents accumulation across iterations)
- Aggressive truncation: Trigger at 65K (keeps only system + last 2 messages)

Multi-iteration protection (NEW):
Without: Iteration 1 (64K) + Iteration 2 tool calls (65K) = 129K ✗ OVERFLOW
With: Truncate to 10K before iteration 2, then + tools (65K) = 75K ✓ SAFE

This ensures: Fixed (30K) + Tool Results (75K max) + Completion (16K) = ~121K < 128K
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable, Tuple, Iterator
import logging
import json
import tiktoken

from utils.langchain_base import BaseLangChainRunnable
from utils.langchain_chat_models import ChatModelRunnable
from utils.langchain_tools import ToolCollectionRunnable

logger = logging.getLogger(__name__)


def count_tokens(messages: List[Dict[str, Any]], model: str = "gpt-4") -> int:
    """
    Count tokens in messages using tiktoken.
    
    Args:
        messages: List of message dicts
        model: Model name for tokenizer
    
    Returns:
        Approximate token count
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")  # Default for GPT-4
    
    num_tokens = 0
    for message in messages:
        # Per message overhead (role + formatting)
        num_tokens += 4
        
        for key, value in message.items():
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
            elif isinstance(value, list) and key == "tool_calls":
                # Count tool calls
                for tool_call in value:
                    if isinstance(tool_call, dict):
                        num_tokens += len(encoding.encode(json.dumps(tool_call)))
    
    # Per-response overhead
    num_tokens += 2
    
    return num_tokens


def truncate_tool_results(
    processed_data: Any,
    max_tokens: int = 30000,
    model: str = "gpt-4"
) -> Any:
    """
    Truncate tool results to fit within token budget.
    
    Args:
        processed_data: Tool result data (dict, list, or string)
        max_tokens: Maximum tokens allowed for this tool result
        model: Model name for tokenizer
    
    Returns:
        Truncated data that fits within max_tokens
    """
    # CRITICAL: Check if vector store result (skip truncation for semantic search results)
    if isinstance(processed_data, dict) and processed_data.get("_skip_truncation"):
        # logger.info("[Token Management] Skipping truncation for vector store result")
        processed_data.pop("_skip_truncation", None)
        return processed_data  # Already doing this - just verify it works
    
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Convert to JSON string
    json_str = json.dumps(processed_data, ensure_ascii=False, default=str)
    tokens = encoding.encode(json_str)
    
    if len(tokens) <= max_tokens:
        return processed_data
    
    # Log truncation
    logger.warning(
        f"[Token Management] Truncating tool result: {len(tokens)} tokens -> {max_tokens} tokens "
        f"({len(tokens) - max_tokens} tokens removed)"
    )
    
    # Truncate and add indicator
    truncated_tokens = tokens[:max_tokens]
    truncated_str = encoding.decode(truncated_tokens)
    
    # Try to parse back to JSON, fallback to string
    try:
        truncated_data = json.loads(truncated_str)
        if isinstance(truncated_data, dict):
            truncated_data["_truncated"] = True
            truncated_data["_original_tokens"] = len(tokens)
            truncated_data["_kept_tokens"] = max_tokens
        return truncated_data
    except:
        return {
            "truncated_content": truncated_str,
            "_truncated": True,
            "_original_tokens": len(tokens),
            "_kept_tokens": max_tokens
        }



class AgentRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible agent that orchestrates chat model + tools + memory.
    
    This wraps our existing agent loop (_agent_loop) as a Runnable, making it
    composable with LCEL chains while maintaining exact current behavior.
    
    Input format:
        {
            "user_input": str,  # user query
            "messages": Optional[List[Dict]],  # conversation history
            "context": Optional[Dict[str, Any]]  # additional context
        }
    
    Output format:
        {
            "success": bool,
            "message": str,  # final response
            "intermediate_steps": Optional[List[Dict]],  # if return_steps=True
            "providers": Dict[str, Any],  # metadata about providers used
            "iterations": int  # number of agent iterations
        }
    
    Example:
        agent = AgentRunnable(
            chat_model=chat_model_runnable,
            tools=tool_collection,
            system_message="You are a helpful assistant",
            max_iterations=5
        )
        
        result = agent.invoke({
            "user_input": "Search for information about n8n"
        })
    """
    
    def __init__(
        self,
        chat_model: ChatModelRunnable,
        tools: ToolCollectionRunnable,
        system_message: str = "You are a helpful AI assistant.",
        max_iterations: int = 5,
        return_intermediate_steps: bool = False,
        enable_multi_turn_tools: bool = True,
        memory: Optional[Dict[str, Any]] = None,  # DEPRECATED: Use memory_runnable
        memory_runnable: Optional[Any] = None,  # NEW: MemoryRunnable instance
        name: Optional[str] = None,
        # Inject agent loop dependencies
        agent_loop_fn: Optional[Callable] = None,
        event_publisher: Optional[Any] = None,  # AgentEventPublisher
        **kwargs: Any
    ):
        """
        Initialize Agent Runnable.
        
        Args:
            chat_model: Chat model Runnable
            tools: Tool collection Runnable
            system_message: System prompt
            max_iterations: Maximum agent iterations
            return_intermediate_steps: Whether to return tool call details
            enable_multi_turn_tools: Allow tools across multiple turns
            memory: DEPRECATED - Use memory_runnable instead
            memory_runnable: MemoryRunnable instance for conversation history
            name: Optional agent name
            agent_loop_fn: Optional custom agent loop function
            event_publisher: Optional AgentEventPublisher for streaming events
            **kwargs: Additional config
        """
        super().__init__(name=name or "Agent", **kwargs)
        self.chat_model = chat_model
        self.tools = tools
        self.system_message = system_message
        self.max_iterations = max_iterations
        self.return_intermediate_steps = return_intermediate_steps
        self.enable_multi_turn_tools = enable_multi_turn_tools
        self.memory = memory  # Keep for backward compat
        self.memory_runnable = memory_runnable  # NEW
        self.agent_loop_fn = agent_loop_fn  # For dependency injection
        self.event_publisher = event_publisher  # For streaming events
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the agent.
        
        Args:
            input: Dict with "user_input" and optional context
            config: Runtime config
        
        Returns:
            Dict with success, message, and optional intermediate_steps
        """
        user_input = input.get("user_input", "")
        if not user_input:
            return {
                "success": False,
                "error": "No user input provided",
                "message": "",
                "intermediate_steps": [],  # Always return empty list for debugging
                "iterations": 0,
                "total_tokens": 0
            }
        
        # Get conversation history (from memory or input)
        messages = input.get("messages", [])
        if not messages:
            # NEW: Use memory_runnable if available
            if self.memory_runnable:
                messages = self._load_memory_via_runnable(user_input)
            # DEPRECATED: Fallback to old memory dict
            elif self.memory:
                messages = self._load_memory(user_input)
        
        # Build initial messages
        messages = self._build_initial_messages(user_input, messages)
        
        # Get tool schemas
        tool_schemas = self.tools.get_tool_schemas(format="openai")
        
        # Execute agent loop
        try:
            result = self._execute_agent_loop(
                messages=messages,
                tool_schemas=tool_schemas,
                user_input=user_input
            )
            
            # Save to memory if configured
            if result.get("success"):
                # NEW: Use memory_runnable if available
                if self.memory_runnable:
                    self._save_memory_via_runnable(messages, result)
                # DEPRECATED: Fallback to old memory dict
                elif self.memory:
                    self._save_memory(messages, result)
            
            return result
            
        except Exception as e:
            logger.error(f"[AgentRunnable] Execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "",
                "intermediate_steps": [],  # Always return empty list for debugging
                "iterations": 0,
                "total_tokens": 0
            }
    
    def _build_initial_messages(
        self,
        user_input: str,
        history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build initial message list for agent.
        
        Args:
            user_input: Current user input
            history: Conversation history
        
        Returns:
            Complete message list
        """
        messages = []
        
        # System message
        if self.system_message:
            messages.append({
                "role": "system",
                "content": self.system_message
            })
        
        # Conversation history - sanitize any empty tool_calls arrays
        # (These could be loaded from memory and cause OpenAI API errors)
        for msg in history:
            sanitized_msg = dict(msg)
            if "tool_calls" in sanitized_msg and not sanitized_msg["tool_calls"]:
                del sanitized_msg["tool_calls"]
            messages.append(sanitized_msg)
        
        # Current user input
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        return messages
    
    def _execute_agent_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
        user_input: str
    ) -> Dict[str, Any]:
        """
        Execute the agent reasoning loop with safeguards.
        
        This is the core agent logic that:
        1. Calls the model
        2. Executes tools if requested
        3. Continues until model provides final answer or max iterations
        4. Enforces max_total_tokens and per-tool timeout limits
        
        Args:
            messages: Current message history
            tool_schemas: Available tool schemas
            user_input: Original user query
        
        Returns:
            Agent execution result with safeguards enforced
        """
        intermediate_steps = []
        iterations = 0
        total_tokens = 0
        
        # Get safeguard config from _config
        # CRITICAL: Lower limit to 95K to account for:
        # - System prompt: 7-10K tokens
        # - Tool schemas: 10-15K tokens
        # - Memory overhead and message formatting: 5-8K tokens
        # Total overhead: ~25-30K, so 95K + 30K ≈ 125K (safe buffer under 128K)
        max_total_tokens = self._config.get("max_total_tokens", 95000)
        max_tool_result_tokens = self._config.get("max_tool_result_tokens", 25000)
        tool_timeout = self._config.get("tool_timeout", 60)  # seconds
        
        while iterations < self.max_iterations:
            iterations += 1
            
            # OPTIMIZATION: Removed agent_step event publishing to reduce RabbitMQ overhead
            # Only final result will be published by the engine
            
            # PROACTIVE TOKEN CHECK: Count tokens before API call
            current_tokens = count_tokens(messages, model="gpt-4")
            
            # MULTI-ITERATION PROTECTION: On iteration 2+, be MORE aggressive to prevent accumulation
            # First iteration typically uses 2-5K tokens, second iteration adds tool results (60K+)
            # Must truncate MORE aggressively on second iteration to prevent 128K overflow
            if iterations > 1 and current_tokens > 50000:
                logger.warning(
                    f"[AgentRunnable] Iteration {iterations}: High token count {current_tokens}. "
                    f"Aggressive multi-iteration truncation to prevent accumulation."
                )
                # On iteration 2+, keep only: system + last user query + last assistant response
                # This removes all previous tool calls and results from iteration 1
                if len(messages) > 3:
                    messages = [messages[0]] + messages[-2:]  # system + last 2 messages
                    current_tokens = count_tokens(messages, model="gpt-4")
                    #logger.info(f"[AgentRunnable] After multi-iteration truncation: {current_tokens} tokens")
            
            # AGGRESSIVE TRUNCATION: Account for large system prompts (7-10K tokens)
            # Safe threshold: 65K (leaves room for tool results ~25K + completion 16K + schemas 15K)
            elif current_tokens > 65000:
                logger.warning(
                    f"[AgentRunnable] High token count BEFORE API call: "
                    f"{current_tokens} tokens. Truncating message history to prevent overflow."
                )
                # Keep only system + last 2 messages (most aggressive for safety)
                if len(messages) > 3:
                    messages = [messages[0]] + messages[-2:]  # system + last 2 messages
                    current_tokens = count_tokens(messages, model="gpt-4")
                    #logger.info(f"[AgentRunnable] After aggressive truncation: {current_tokens} tokens")
            elif current_tokens > max_total_tokens:
                logger.warning(
                    f"[AgentRunnable] Token limit exceeded BEFORE API call: "
                    f"{current_tokens} > {max_total_tokens}. Truncating message history."
                )
                # Remove oldest messages (keep system + last 4)
                if len(messages) > 5:
                    messages = [messages[0]] + messages[-4:]  # system + last 4 messages
                    current_tokens = count_tokens(messages, model="gpt-4")
                    logger.info(f"[AgentRunnable] After truncation: {current_tokens} tokens")
            
            # Determine if tools should be provided this turn
            current_tools = tool_schemas if (
                self.enable_multi_turn_tools or iterations == 1
            ) else None
            
            # Call chat model
            model_result = self.chat_model.invoke({
                "messages": messages,
                "tools": current_tools
            })
            
            # Check token usage and enforce max_total_tokens
            usage = model_result.get("usage", {})
            call_tokens = usage.get("total_tokens", 0)
            total_tokens += call_tokens

            #logger.info(
            #    f"[AgentRunnable] Iteration {iterations}: Used {call_tokens} tokens "
            #    f"(total: {total_tokens}/{max_total_tokens})"
            #)

            if total_tokens > max_total_tokens:
                # OPTIMIZATION: Removed agent_error event publishing
                
                return {
                    "success": False,
                    "error": "Token limit exceeded",
                    "iterations": iterations,
                    "total_tokens": total_tokens,
                    "max_total_tokens": max_total_tokens,
                    "intermediate_steps": intermediate_steps  # Always return for debugging
                }
            
            # Check for errors
            if "error" in model_result:
                return {
                    "success": False,
                    "error": model_result["error"],
                    "message": "",
                    "intermediate_steps": intermediate_steps,  # Always return for debugging
                    "iterations": iterations,
                    "total_tokens": total_tokens  # Include tokens tracked before error
                }
            
            assistant_msg = model_result.get("assistant_message", {})
            tool_calls_from_msg = assistant_msg.get("tool_calls", []) or []
            
            # Model requested tools
            if tool_calls_from_msg:
                # Convert tool_calls back to OpenAI format for the conversation
                # The model returns: {"id": "...", "name": "...", "arguments": {...}}
                # But OpenAI expects: {"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}
                openai_tool_calls = []
                for tc in tool_calls_from_msg:
                    openai_tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("arguments", {}))
                        }
                    })
                
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": self._extract_content_string(assistant_msg),
                    "tool_calls": openai_tool_calls
                })
                
                # Execute each tool with flattened format
                for tool_call in tool_calls_from_msg:
                    # tool_calls_from_msg is already in flattened format from adapter:
                    # {"id": str, "name": str, "arguments": dict}
                    tool_id = tool_call.get("id", "")
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})
                    
                    if not tool_name:
                        logger.error(f"[AgentRunnable] Tool call missing name: {tool_call}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": "unknown",
                            "content": json.dumps({
                                "ok": False,
                                "error": "Tool name is missing"
                            })
                        })
                        continue
                    
                    # OPTIMIZATION: Removed tool_called event publishing
                    
                    # Execute tool via collection with timeout
                    import signal
                    import threading
                    
                    tool_result = None
                    timeout_error = None
                    
                    def execute_with_timeout():
                        nonlocal tool_result
                        try:
                            tool_result = self.tools.invoke({
                                "tool_name": tool_name,
                                "arguments": tool_args,
                                "tool_call_id": tool_id,
                                "context": {
                                    "user_query": user_input,
                                    "assistant_text": self._extract_content_string(assistant_msg)
                                }
                            })
                        except Exception as e:
                            tool_result = {
                                "ok": False,
                                "name": tool_name,
                                "tool_call_id": tool_id,
                                "error": {
                                    "type": "ExecutionError",
                                    "message": str(e),
                                    "details": []
                                }
                            }
                    
                    # Execute in thread with timeout
                    exec_thread = threading.Thread(target=execute_with_timeout)
                    exec_thread.daemon = True
                    exec_thread.start()
                    exec_thread.join(timeout=tool_timeout)
                    
                    if exec_thread.is_alive():
                        # Timeout occurred
                        logger.warning(f"[AgentRunnable] Tool {tool_name} timed out after {tool_timeout}s")
                        tool_result = {
                            "ok": False,
                            "name": tool_name,
                            "tool_call_id": tool_id,
                            "error": {
                                "type": "TimeoutError",
                                "message": f"Tool execution timed out after {tool_timeout}s",
                                "details": []
                            }
                        }
                    
                    # Ensure tool_result is set
                    if tool_result is None:
                        tool_result = {
                            "ok": False,
                            "name": tool_name,
                            "tool_call_id": tool_id,
                            "error": {
                                "type": "UnknownError",
                                "message": "Tool execution failed silently",
                                "details": []
                            }
                        }
                    
                    # Process tool response with smart filtering (like existing implementation)
                    if tool_result.get("ok"):
                        raw_data = tool_result.get("data")
                        processed_data = self._process_tool_response(
                            tool_name=tool_name,
                            raw_result=raw_data,
                            user_query=user_input,
                            assistant_text=self._extract_content_string(assistant_msg)
                        )
                        
                        # TOKEN MANAGEMENT: Truncate large tool results to prevent context overflow
                        processed_data = truncate_tool_results(
                            processed_data,
                            max_tokens=max_tool_result_tokens,
                            model="gpt-4"
                        )
                        
                        # OPTIMIZATION: Removed tool_result event publishing (success)
                        
                        # Add successful tool result message
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": json.dumps(processed_data, ensure_ascii=False, default=str)
                        })
                        
                        # Track intermediate step
                        if self.return_intermediate_steps:
                            intermediate_steps.append({
                                "action": {
                                    "tool": tool_name,
                                    "tool_input": tool_args
                                },
                                "observation": processed_data
                            })
                    else:
                        # Add error tool result message
                        error_info = tool_result.get("error", {})
                        
                        # OPTIMIZATION: Removed tool_result event publishing (error)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": json.dumps({
                                "error": error_info.get("message", "Tool execution failed"),
                                "details": error_info.get("details", [])
                            }, ensure_ascii=False)
                        })
                        
                        # Track error in intermediate steps
                        if self.return_intermediate_steps:
                            intermediate_steps.append({
                                "action": {
                                    "tool": tool_name,
                                    "tool_input": tool_args
                                },
                                "observation": {"error": error_info}
                            })
                
                # TOKEN CHECK AFTER ADDING TOOL RESULTS: Check if we're approaching the limit
                messages_with_tools_tokens = count_tokens(messages, model="gpt-4")
                if messages_with_tools_tokens > 85000:  # Leave 40K for completion + overhead
                    logger.warning(
                        f"[AgentRunnable] High token count AFTER tool results: "
                        f"{messages_with_tools_tokens} tokens. Truncating old messages."
                    )
                    # Keep system message + only the most recent exchange (user query + tool calls + tool results)
                    # Find the last user message index
                    last_user_idx = None
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i].get("role") == "user":
                            last_user_idx = i
                            break
                    
                    if last_user_idx is not None and last_user_idx > 1:
                        # Keep system (0) + everything from last user message onwards
                        messages = [messages[0]] + messages[last_user_idx:]
                        messages_with_tools_tokens = count_tokens(messages, model="gpt-4")
                        # logger.info(
                        #     f"[AgentRunnable] After tool-result truncation: {messages_with_tools_tokens} tokens "
                        #     f"(kept system + last {len(messages) - 1} messages)"
                        # )
                
                # Continue loop to let model read tool outputs
                continue
            
            # No tool calls - final answer
            final_message = self._extract_content_string(assistant_msg)
            
            # Check if response is empty or too short (might indicate truncation)
            if not final_message or len(final_message.strip()) < 10:
                logger.error(
                    f"[AgentRunnable] Empty or truncated response received. "
                    f"Message length: {len(final_message) if final_message else 0}, "
                    f"Total tokens: {total_tokens}"
                )
                return {
                    "success": False,
                    "error": "Response was empty or truncated. Please try a more specific question.",
                    "message": final_message or "",
                    "intermediate_steps": intermediate_steps,
                    "iterations": iterations,
                    "total_tokens": total_tokens
                }
            
            # CRITICAL FIX: Remove empty tool_calls array before appending to messages
            # OpenAI API rejects messages with empty tool_calls arrays
            sanitized_msg = dict(assistant_msg)
            if "tool_calls" in sanitized_msg and not sanitized_msg["tool_calls"]:
                del sanitized_msg["tool_calls"]
            messages.append(sanitized_msg)
            
            # OPTIMIZATION: Removed model_result event publishing
            
            # OPTIMIZATION: Removed agent_completed event publishing
            
            return {
                "success": True,
                "message": final_message,
                "intermediate_steps": intermediate_steps,  # Always return for debugging
                "iterations": iterations,
                "total_tokens": total_tokens,
                "providers": self._build_providers_meta()
            }
        
        # OPTIMIZATION: Removed agent_error event publishing for max iterations
        
        return {
            "success": False,
            "error": "Maximum iterations reached",
            "message": "",
            "intermediate_steps": intermediate_steps,  # Always return for debugging
            "iterations": iterations,
            "total_tokens": total_tokens
        }
    
    def _process_tool_response(
        self,
        tool_name: str,
        raw_result: Any,
        user_query: str,
        assistant_text: str = ""
    ) -> Any:
        """
        Process tool response with smart filtering for large result sets.
        
        This applies the same logic as the existing AI Agent implementation:
        - Filters large lists based on relevance to user query
        - Truncates long text fields
        - Removes binary/large content
        
        Args:
            tool_name: Name of the tool
            raw_result: Raw tool execution result
            user_query: User's original query
            assistant_text: Assistant's text before tool call
        
        Returns:
            Processed result (filtered/truncated as needed)
        """
        try:
            # Import the existing process_tool_response function
            from utils.ai_agent_tool_ops import process_tool_response
            
            # Use the same logic as existing implementation
            processed = process_tool_response(
                tool_key=tool_name.lower(),
                tool_name=tool_name,
                response=raw_result,
                user_query=user_query or assistant_text or ""
            )
            
            return processed
            
        except Exception as e:
            logger.warning(f"[AgentRunnable] Error processing tool response: {e}")
            # Fallback to raw result if processing fails
            return raw_result
    
    def _extract_content_string(self, assistant_msg: Dict[str, Any]) -> str:
        """
        Extract plain text content from assistant message.
        
        Args:
            assistant_msg: Assistant message (may have array or string content)
        
        Returns:
            Plain string content
        """
        content = assistant_msg.get("content", "")
        if isinstance(content, list):
            # Extract text from array format [{"type": "text", "text": str}, ...]
            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(part.get("text", ""))
            return "".join(texts)
        return str(content) if content else ""
    
    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """
        Format tool execution result for model consumption.
        
        Args:
            result: Tool execution result
        
        Returns:
            Formatted string
        """
        if result.get("success"):
            tool_output = result.get("result", "")
            if isinstance(tool_output, dict):
                return json.dumps(tool_output, ensure_ascii=False)
            return str(tool_output)
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    
    def _load_memory_via_runnable(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Load conversation history via MemoryRunnable.
        
        Args:
            user_input: Current user input (for context)
        
        Returns:
            List of messages from memory
        """
        try:
            result = self.memory_runnable.invoke({
                "action": "load",
                "user_input": user_input
            })
            
            if result.get("success"):
                return result.get("messages", [])
            else:
                logger.warning(f"[AgentRunnable] Memory load failed: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.warning(f"[AgentRunnable] Memory load exception: {e}")
            return []
    
    def _load_memory(self, user_input: str) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Load conversation history from memory dict.
        Use _load_memory_via_runnable instead.
        
        Args:
            user_input: Current user input (for context)
        
        Returns:
            List of messages from memory
        """
        if not self.memory:
            return []
        
        try:
            from nodes.memory.buffer_memory import MemoryManager
            
            session_id = self.memory.get("session_id", "default")
            window = self.memory.get("context_window_length", 5)
            
            messages = MemoryManager.load(session_id, window)
            return messages
            
        except Exception as e:
            logger.warning(f"[AgentRunnable] Memory load failed: {e}")
            return []
    
    def _save_memory_via_runnable(
        self,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any]
    ) -> None:
        """
        Save conversation to memory via MemoryRunnable.
        
        Args:
            messages: Full message history
            result: Agent execution result
        """
        try:
            # Filter messages for memory (remove only system messages)
            # IMPORTANT: Keep tool messages! OpenAI requires tool responses after tool_calls
            memory_messages = [
                m for m in messages
                if m.get("role") != "system"
            ]
            
            save_result = self.memory_runnable.invoke({
                "action": "save",
                "messages": memory_messages
            })
            
            # FIXED: Check "success" not "ok" (MemoryRunnable returns "success" key)
            if not save_result.get("success"):
                logger.warning(f"[AgentRunnable] Memory save failed: {save_result.get('error')}")
                
        except Exception as e:
            logger.warning(f"[AgentRunnable] Memory save exception: {e}")
    
    def _save_memory(
        self,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any]
    ) -> None:
        """
        DEPRECATED: Save conversation to memory dict.
        Use _save_memory_via_runnable instead.
        
        Args:
            messages: Full message history
            result: Agent execution result
        """
        if not self.memory:
            return
        
        try:
            from nodes.memory.buffer_memory import MemoryManager
            
            session_id = self.memory.get("session_id", "default")
            ttl = self.memory.get("ttl_seconds", MemoryManager.DEFAULT_TTL_SECONDS)
            context_window = self.memory.get("context_window_length", 5)
            
            # Filter messages for memory (remove only system messages)
            # IMPORTANT: Keep tool messages! OpenAI requires tool responses after tool_calls
            memory_messages = [
                m for m in messages
                if m.get("role") != "system"
            ]
            
            # CRITICAL FIX: Pass context_window to save() to prevent unbounded accumulation
            # auto_clear_on_full=True: When window is full, clear and start fresh
            MemoryManager.save(
                session_id, 
                memory_messages, 
                ttl_seconds=ttl,
                context_window=context_window,
                auto_clear_on_full=True  # Clear cache when full, start fresh
            )
            
        except Exception as e:
            logger.warning(f"[AgentRunnable] Memory save failed: {e}")
    
    def _get_metadata(self) -> Dict[str, Any]:
        """
        Override: Provide agent-specific metadata.
        
        Returns:
            Metadata about agent configuration
        """
        return {
            "runnable_type": "AgentRunnable",
            "runnable_name": self.name,
            "model": {
                "provider": self.chat_model.provider,
                "model": self.chat_model.model,
                "temperature": self.chat_model.temperature
            },
            "tools": list(self.tools.tools.keys()),
            "memory": self.memory.get("type") if self.memory else None,
            "max_iterations": self.max_iterations
        }
    
    def _build_providers_meta(self) -> Dict[str, Any]:
        """Build metadata about providers used (DEPRECATED - use _get_metadata)"""
        return {
            "model": {
                "provider": self.chat_model.provider,
                "model": self.chat_model.model,
                "temperature": self.chat_model.temperature
            },
            "tools": list(self.tools.tools.keys()),
            "memory": self.memory.get("type") if self.memory else None
        }
    
    def with_memory(self, memory: Dict[str, Any]) -> "AgentRunnable":
        """
        DEPRECATED: Create a new agent with memory dict configured.
        Use with_memory_runnable() instead.
        
        Args:
            memory: Memory configuration dict
        
        Returns:
            New AgentRunnable instance
        """
        return AgentRunnable(
            chat_model=self.chat_model,
            tools=self.tools,
            system_message=self.system_message,
            max_iterations=self.max_iterations,
            return_intermediate_steps=self.return_intermediate_steps,
            enable_multi_turn_tools=self.enable_multi_turn_tools,
            memory=memory,
            name=self.name,
            agent_loop_fn=self.agent_loop_fn,
            **self._config
        )
    
    def with_memory_runnable(self, memory_runnable: Any) -> "AgentRunnable":
        """
        Create a new agent with MemoryRunnable configured.
        
        Args:
            memory_runnable: MemoryRunnable instance
        
        Returns:
            New AgentRunnable instance
        """
        return AgentRunnable(
            chat_model=self.chat_model,
            tools=self.tools,
            system_message=self.system_message,
            max_iterations=self.max_iterations,
            return_intermediate_steps=self.return_intermediate_steps,
            enable_multi_turn_tools=self.enable_multi_turn_tools,
            memory_runnable=memory_runnable,
            name=self.name,
            agent_loop_fn=self.agent_loop_fn,
            event_publisher=self.event_publisher,
            **self._config
        )
    
    def with_tools(self, tools: ToolCollectionRunnable) -> "AgentRunnable":
        """
        Create a new agent with different tools.
        
        Args:
            tools: New tool collection
        
        Returns:
            New AgentRunnable instance
        """
        return AgentRunnable(
            chat_model=self.chat_model,
            tools=tools,
            system_message=self.system_message,
            max_iterations=self.max_iterations,
            return_intermediate_steps=self.return_intermediate_steps,
            enable_multi_turn_tools=self.enable_multi_turn_tools,
            memory=self.memory,
            name=self.name,
            agent_loop_fn=self.agent_loop_fn,
            event_publisher=self.event_publisher,
            **self._config
        )
    
    def stream(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream agent execution as structured events.
        
        Yields event dictionaries with "type" field:
        - {"type": "agent_started", ...}
        - {"type": "agent_step", ...}
        - {"type": "model_result", "usage": {...}, ...}
        - {"type": "tool_called", "name": str, "args": {...}, ...}
        - {"type": "tool_result", "name": str, "ok": bool, ...}
        - {"type": "agent_completed", "final_preview": str, ...}
        - {"type": "agent_error", "message": str, ...}
        - {"type": "result", "data": {...}}  # Final result
        
        Args:
            input: Same as invoke()
            config: Runtime config
        
        Yields:
            Structured event dictionaries
        """
        user_input = input.get("user_input", "")
        if not user_input:
            yield {
                "type": "agent_error",
                "message": "No user input provided"
            }
            yield {
                "type": "result",
                "data": {
                    "success": False,
                    "error": "No user input provided",
                    "message": ""
                }
            }
            return
        
        # OPTIMIZATION: Removed agent_started event publishing
        yield {
            "type": "agent_started",
            "model": f"{self.chat_model.provider}/{self.chat_model.model}",
            "tools_count": len(self.tools.tools)
        }
        
        # Execute agent loop with event streaming
        try:
            result = self.invoke(input, config)
            
            # Emit final result
            yield {
                "type": "result",
                "data": result
            }
            
        except Exception as e:
            logger.error(f"[AgentRunnable] Streaming error: {e}")
            
            # OPTIMIZATION: Removed agent_error event publishing
            yield {
                "type": "agent_error",
                "message": str(e),
                "fatal": True
            }
            
            # Emit error result
            yield {
                "type": "result",
                "data": {
                    "success": False,
                    "error": str(e),
                    "message": ""
                }
            }
    
    def __repr__(self) -> str:
        return (
            f"AgentRunnable("
            f"model={self.chat_model.model}, "
            f"tools={len(self.tools.tools)}, "
            f"max_iter={self.max_iterations}"
            f")"
        )


# ============================================================================
# Factory Functions
# ============================================================================

def create_agent(
    chat_model: ChatModelRunnable,
    tools: ToolCollectionRunnable,
    system_message: str = "You are a helpful AI assistant.",
    **kwargs: Any
) -> AgentRunnable:
    """
    Factory function to create an AgentRunnable.
    
    Args:
        chat_model: Chat model to use
        tools: Available tools
        system_message: System prompt
        **kwargs: Additional agent configuration
    
    Returns:
        AgentRunnable instance
    """
    return AgentRunnable(
        chat_model=chat_model,
        tools=tools,
        system_message=system_message,
        **kwargs
    )
