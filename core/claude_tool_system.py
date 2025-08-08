import json
import re
import time
import logging
from typing import Dict, List, Any, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from tools.tool_registry import TOOL_REGISTRY
from core.tool_validator import tool_validator
from tracking.tracker import tracker

logger = logging.getLogger(__name__)

@dataclass
class ToolCall:
    """Structured representation of a tool call"""
    name: str
    args: Dict[str, Any]
    id: Optional[str] = None
    
@dataclass
class ToolResult:
    """Structured representation of a tool result"""
    tool_call: ToolCall
    result: Any
    success: bool
    error: Optional[str] = None
    execution_time: float = 0.0

class ClaudeToolSystem:
    """
    Advanced tool calling system that mimics Claude Code's behavior:
    - Parallel execution of independent tools
    - Structured tool call parsing
    - Intelligent conversation flow management
    - Comprehensive error handling and recovery
    """
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.conversation_context = []
        self.tool_execution_history = []
    
    def parse_tool_calls(self, response: str) -> List[ToolCall]:
        """
        Parse tool calls from AI response using multiple patterns.
        Supports both the current TOOL_CALL format and function call format.
        """
        tool_calls = []
        
        # Pattern 1: Current format - TOOL_CALL: tool_name\nARGS: {...}
        pattern1 = r'TOOL_CALL:\s*(\w+)\s*[\r\n]+\s*ARGS:\s*(\{[\s\S]*?\})'
        matches1 = re.findall(pattern1, response, re.MULTILINE | re.DOTALL)
        
        # Pattern 1b: Code block format - ```tool_call\nTOOL_CALL: ...\n```
        pattern1b = r'```tool_call\s*[\r\n]+\s*TOOL_CALL:\s*(\w+)\s*[\r\n]+\s*ARGS:\s*(\{[\s\S]*?\})\s*[\r\n]+\s*```'
        matches1b = re.findall(pattern1b, response, re.MULTILINE | re.DOTALL)
        
        for tool_name, args_str in matches1:
            try:
                args = self._safe_json_parse(args_str)
                tool_calls.append(ToolCall(name=tool_name, args=args))
            except Exception as e:
                logger.error(f"Failed to parse tool call {tool_name}: {e}")
        
        for tool_name, args_str in matches1b:
            try:
                args = self._safe_json_parse(args_str)
                tool_calls.append(ToolCall(name=tool_name, args=args))
            except Exception as e:
                logger.error(f"Failed to parse tool call {tool_name}: {e}")
        
        # Pattern 2: Function call format - <function_calls>...<invoke name="tool">...
        pattern2 = r'<invoke name="([^"]+)"[^>]*>(.*?)</invoke>'
        matches2 = re.findall(pattern2, response, re.DOTALL)
        
        for tool_name, params_block in matches2:
            try:
                args = self._parse_function_parameters(params_block)
                tool_calls.append(ToolCall(name=tool_name, args=args))
            except Exception as e:
                logger.error(f"Failed to parse function call {tool_name}: {e}")
        
        # Pattern 3: JSON array format - [{"tool": "name", "args": {...}}]  
        # Look for JSON arrays in code blocks first (more specific)
        json_pattern1 = r'```json\s*\n([\s\S]*?)\n\s*```'
        json_matches1 = re.findall(json_pattern1, response, re.DOTALL)
        
        # Remove JSON code blocks from response to avoid duplicate parsing
        response_without_json_blocks = re.sub(json_pattern1, '', response, flags=re.DOTALL)
        
        # Then look for standalone JSON arrays
        json_pattern2 = r'\[[\s\S]*?\]'
        json_matches2 = re.findall(json_pattern2, response_without_json_blocks)
        
        all_json_matches = json_matches1 + json_matches2
        
        for json_str in all_json_matches:
            try:
                calls_data = json.loads(json_str.strip())
                if isinstance(calls_data, list):
                    for call_data in calls_data:
                        if isinstance(call_data, dict) and 'tool' in call_data and 'args' in call_data:
                            tool_calls.append(ToolCall(
                                name=call_data['tool'],
                                args=call_data['args']
                            ))
            except Exception as e:
                logger.debug(f"Failed to parse JSON tool calls: {e}")  # Changed to debug to reduce noise
        
        # Remove duplicates while preserving order
        seen = set()
        unique_calls = []
        for call in tool_calls:
            call_signature = f"{call.name}_{hash(frozenset(call.args.items()) if call.args else frozenset())}"
            if call_signature not in seen:
                seen.add(call_signature)
                unique_calls.append(call)
        
        return unique_calls
    
    def _safe_json_parse(self, args_str: str) -> Dict[str, Any]:
        """Safely parse JSON arguments with fallback handling"""
        try:
            return json.loads(args_str)
        except json.JSONDecodeError:
            # Fallback: handle literal newlines
            escaped_args_str = args_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            args = json.loads(escaped_args_str)
            
            # Unescape string values
            for key, value in args.items():
                if isinstance(value, str):
                    args[key] = value.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
            
            return args
    
    def _parse_function_parameters(self, params_block: str) -> Dict[str, Any]:
        """Parse function call parameters from XML-like format"""
        args = {}
        param_pattern = r'<parameter name="([^"]+)">(.*?)</parameter>'
        matches = re.findall(param_pattern, params_block, re.DOTALL)
        
        for param_name, param_value in matches:
            # Try to parse as JSON, otherwise use as string
            param_value = param_value.strip()
            try:
                args[param_name] = json.loads(param_value)
            except json.JSONDecodeError:
                args[param_name] = param_value
        
        return args
    
    def execute_tools_parallel(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute tool calls in parallel when possible, sequential when dependencies exist.
        This mimics Claude Code's intelligent execution strategy.
        """
        if not tool_calls:
            return []
        
        # Group tools by dependency - file operations should be sequential on same file
        independent_groups, dependent_chains = self._analyze_dependencies(tool_calls)
        
        all_results = []
        
        # Execute independent groups in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            # Submit independent tools
            for group in independent_groups:
                for tool_call in group:
                    future = executor.submit(self._execute_single_tool, tool_call)
                    futures.append((future, tool_call))
            
            # Collect results as they complete
            for future, tool_call in futures:
                try:
                    result = future.result(timeout=30)  # 30s timeout per tool
                    all_results.append(result)
                except Exception as e:
                    error_result = ToolResult(
                        tool_call=tool_call,
                        result=None,
                        success=False,
                        error=str(e)
                    )
                    all_results.append(error_result)
        
        # Execute dependent chains sequentially
        for chain in dependent_chains:
            for tool_call in chain:
                result = self._execute_single_tool(tool_call)
                all_results.append(result)
        
        return all_results
    
    def _analyze_dependencies(self, tool_calls: List[ToolCall]) -> Tuple[List[List[ToolCall]], List[List[ToolCall]]]:
        """
        Analyze tool calls for dependencies and group them accordingly.
        Returns (independent_groups, dependent_chains)
        """
        independent_groups = []
        dependent_chains = []
        
        # Simple heuristic: file operations on same file are dependent
        file_operations = {}
        other_tools = []
        
        for tool_call in tool_calls:
            if tool_call.name in ['read_file', 'write_file', 'edit_file']:
                file_path = (tool_call.args.get('path') or 
                           tool_call.args.get('arg1') or 
                           tool_call.args.get('arg'))
                
                if file_path:
                    if file_path not in file_operations:
                        file_operations[file_path] = []
                    file_operations[file_path].append(tool_call)
                else:
                    other_tools.append(tool_call)
            else:
                other_tools.append(tool_call)
        
        # File operations on same file form dependent chains
        for file_path, operations in file_operations.items():
            if len(operations) > 1:
                dependent_chains.append(operations)
            else:
                independent_groups.append(operations)
        
        # Other tools can run independently
        if other_tools:
            independent_groups.append(other_tools)
        
        return independent_groups, dependent_chains
    
    def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with validation and error handling"""
        start_time = time.time()
        
        try:
            # Validate tool call
            should_execute, block_reason = tool_validator.validate_tool_call(
                tool_call.name, tool_call.args
            )
            
            if not should_execute:
                return ToolResult(
                    tool_call=tool_call,
                    result=f"Blocked: {block_reason}",
                    success=False,
                    error=block_reason,
                    execution_time=time.time() - start_time
                )
            
            # Execute tool
            if tool_call.name not in TOOL_REGISTRY:
                return ToolResult(
                    tool_call=tool_call,
                    result=None,
                    success=False,
                    error=f"Tool '{tool_call.name}' not found",
                    execution_time=time.time() - start_time
                )
            
            tool_func = TOOL_REGISTRY[tool_call.name]
            result = self._call_tool_function(tool_func, tool_call.name, tool_call.args)
            
            execution_time = time.time() - start_time
            
            # Record successful execution
            tool_validator.record_tool_call(
                tool_call.name, tool_call.args, str(result), execution_time
            )
            
            return ToolResult(
                tool_call=tool_call,
                result=result,
                success=True,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool execution error for {tool_call.name}: {e}")
            
            return ToolResult(
                tool_call=tool_call,
                result=None,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _call_tool_function(self, tool_func: Callable, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call tool function with proper parameter mapping"""
        # Handle parameter mapping based on tool type
        if tool_name == "read_file":
            path = args.get("path") or args.get("arg1") or args.get("arg")
            if not path:
                raise ValueError("Missing 'path' parameter")
            return tool_func(path)
            
        elif tool_name == "write_file":
            path = args.get("path") or args.get("arg1")
            content = args.get("content") or args.get("edits") or args.get("arg2", "")
            if not path:
                raise ValueError("Missing 'path' parameter")
            return tool_func(path, content)
            
        elif tool_name == "edit_file":
            path = args.get("path") or args.get("arg1")
            action = args.get("action") or args.get("arg2")
            content = args.get("content") or args.get("arg3")
            match_text = args.get("match_text")
            start_line = args.get("start_line")
            end_line = args.get("end_line")
            
            if not path or not action:
                raise ValueError("Missing required parameters (path, action)")
            return tool_func(path, action, content, match_text, start_line, end_line)
            
        elif tool_name == "run_command":
            cmd = args.get("cmd") or args.get("arg1") or args.get("arg")
            if not cmd:
                raise ValueError("Missing 'cmd' parameter")
            return tool_func(cmd)
            
        elif tool_name == "find_files":
            pattern = args.get("pattern") or args.get("arg1") or args.get("arg", "*")
            search_type = args.get("search_type") or args.get("arg2", "name")
            max_results = args.get("max_results") or args.get("arg3", 100)
            return tool_func(pattern, search_type, max_results)
            
        elif tool_name == "list_directory":
            path = args.get("path") or args.get("arg1") or args.get("arg", ".")
            return tool_func(path)
            
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results for display to user"""
        if not results:
            return ""
        
        formatted_results = []
        
        for result in results:
            tool_name = result.tool_call.name
            
            if result.success:
                formatted_results.append(f"{tool_name}: {result.result}")
            else:
                formatted_results.append(f"{tool_name}: Error - {result.error}")
        
        return "\n".join(formatted_results)
    
    def should_continue_conversation(self, results: List[ToolResult]) -> bool:
        """Determine if conversation should continue based on tool results"""
        # Continue if any tool suggests follow-up actions
        for result in results:
            if result.success and result.result:
                result_str = str(result.result).lower()
                # Look for indicators that suggest follow-up might be needed
                if any(indicator in result_str for indicator in [
                    'error', 'failed', 'not found', 'missing', 'incomplete'
                ]):
                    return True
        
        return False
    
    def reset_conversation_context(self):
        """Reset conversation context for new interaction"""
        self.conversation_context.clear()
        tool_validator.reset_context()

# Global instance
claude_tool_system = ClaudeToolSystem()