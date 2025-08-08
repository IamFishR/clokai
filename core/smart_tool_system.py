"""
Smart Tool System - Sophisticated multi-step AI interaction pattern
Implements: User -> AI (intent) -> AI response -> AI (tool details) -> Tool execution
-> (if fail -> AI correction -> retry) -> AI summary -> User
"""

import json
import time
import logging
import re
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from tools.tool_registry import TOOL_REGISTRY
from llm.ollama_client import call_llm, call_llm_stream

logger = logging.getLogger(__name__)

@dataclass
class ToolRequest:
    """Simple tool request structure"""
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(int(time.time() * 1000)))

@dataclass
class ToolResult:
    """Tool execution result"""
    request: ToolRequest
    success: bool
    result: Any = None
    error: str = None
    execution_time: float = 0.0
    cached: bool = False

@dataclass
class ExecutionContext:
    """Context for tool execution session"""
    user_input: str
    tool_requests: List[ToolRequest] = field(default_factory=list)
    results: List[ToolResult] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2

class SmartToolSystem:
    """Smart tool system with intelligent multi-step processing"""
    
    def __init__(self):
        self.cache = {}  # Simple result cache
        self.timeout_seconds = 30  # Tool execution timeout
        self.max_parallel = 3  # Max parallel tool executions
        
    def process_user_request(self, user_input: str, messages: List[Dict]) -> tuple[str, List[ToolResult]]:
        """
        Main entry point - processes user request with full smart workflow
        Returns: (final_response, tool_results)
        """
        print("[DEBUG] SmartToolSystem.process_user_request called")
        try:
            context = ExecutionContext(user_input=user_input)
            
            # Step 1: Check for force keywords first
            if self._has_force_keywords(user_input):
                return self._handle_force_keywords(user_input, messages)
            
            # Step 2: Get initial AI response
            initial_response = self._get_initial_ai_response(user_input, messages)
            
            # Step 3: Check if initial response already contains tools
            initial_tools = self._parse_tools_from_response(initial_response)
            if initial_tools:
                print(f"[TOOLS] Found {len(initial_tools)} tool(s) in initial response")
                tool_requests = initial_tools
            else:
                # Step 3b: Analyze if tools are needed
                if not self._needs_tools(user_input, initial_response):
                    return initial_response, []
                
                # Step 4: Get tool details from AI
                print("[TOOLS] Initial response had no tools, asking AI for tool details...")
                tool_requests = self._extract_tool_requests(user_input, initial_response, messages)
                if not tool_requests:
                    return initial_response, []
                
            context.tool_requests = tool_requests
            
            # Step 5: Execute tools with progress indication
            print(f"[DEBUG] About to execute {len(tool_requests)} tools")
            results = self._execute_tools_with_progress(tool_requests)
            print(f"[DEBUG] Got {len(results)} results back")
            context.results = results
            
            # Step 6: Handle failures with AI correction
            if any(not r.success for r in results):
                corrected_results = self._handle_tool_failures(context, messages)
                if corrected_results:
                    results = corrected_results
            
            # Step 7: Generate AI summary
            print(f"[DEBUG] Generating summary with {len(results)} results")
            final_response = self._generate_summary(user_input, initial_response, results, messages)
            
            print(f"[DEBUG] Returning final_response and {len(results)} results")
            return final_response, results
            
        except Exception as e:
            logger.error(f"Smart tool system error: {e}")
            return f"I encountered an error processing your request: {str(e)}", []
    
    def _has_force_keywords(self, user_input: str) -> bool:
        """Check for force keywords like !read, !run, etc."""
        force_keywords = ['!read', '!write', '!edit', '!run', '!exec', '!find', '!search', '!list', '!ls']
        return any(keyword in user_input.lower() for keyword in force_keywords)
    
    def _handle_force_keywords(self, user_input: str, messages: List[Dict]) -> tuple[str, List[ToolResult]]:
        """Handle force keyword requests directly"""
        print("[FORCE] Processing force keyword request...")
        
        # Extract the force command
        parts = user_input.split(None, 1)
        if len(parts) < 2:
            return "Force command needs an argument (e.g., !read filename.py)", []
        
        keyword = parts[0].lower()
        argument = parts[1]
        
        # Map keywords to tools (using correct parameter names)
        keyword_map = {
            '!read': ('read_file', {'path': argument}),
            '!write': ('write_file', {'path': argument, 'content': 'Please specify content'}),
            '!list': ('list_directory', {'path': argument}),
            '!ls': ('list_directory', {'path': argument}),
            '!run': ('run_command', {'cmd': argument}),
            '!exec': ('run_command', {'cmd': argument}),
            '!find': ('find_files', {'pattern': argument}),
            '!search': ('find_files', {'pattern': argument})
        }
        
        if keyword not in keyword_map:
            return f"Unknown force keyword: {keyword}", []
        
        tool_name, params = keyword_map[keyword]
        request = ToolRequest(action=tool_name, params=params)
        
        # Execute directly
        result = self._execute_single_tool(request)
        
        # Generate simple response
        if result.success:
            return f"Executed {keyword} successfully", [result]
        else:
            return f"Failed to execute {keyword}: {result.error}", [result]
    
    def _get_initial_ai_response(self, user_input: str, messages: List[Dict]) -> str:
        """Get initial AI response without tools"""
        try:
            response_messages = messages + [{"role": "user", "content": user_input}]
            return call_llm_stream(response_messages)
        except Exception as e:
            logger.error(f"Failed to get AI response: {e}")
            return "I'm having trouble processing your request right now."
    
    def _needs_tools(self, user_input: str, ai_response: str) -> bool:
        """Smart detection of whether tools are needed"""
        
        user_lower = user_input.lower()
        
        # Skip obviously non-tool requests
        greeting_patterns = [
            r'^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings?)\s*!?\s*$',
            r'^\s*(how\s+are\s+you|what\'s\s+up|wassup)\s*\??\s*$',
            r'^\s*(thank\s+you|thanks|thx)\s*!?\s*$',
            r'^\s*(bye|goodbye|see\s+you|farewell)\s*!?\s*$'
        ]
        
        if any(re.match(pattern, user_lower, re.IGNORECASE) for pattern in greeting_patterns):
            return False
        
        # Skip general knowledge questions
        knowledge_patterns = [
            r'^\s*what\s+is\s+\w+\s*\??',
            r'^\s*how\s+does\s+\w+\s+work\s*\??',
            r'^\s*explain\s+\w+',
            r'^\s*tell\s+me\s+about\s+\w+'
        ]
        
        if any(re.match(pattern, user_lower, re.IGNORECASE) for pattern in knowledge_patterns):
            # But allow if it mentions files or code
            if not any(word in user_lower for word in ['file', 'code', 'script', 'project', 'directory', '.py', '.js', '.json']):
                return False
        
        # Check user input for obvious tool patterns
        tool_patterns = [
            r'\b(read|show|display|view|see|check|examine)\s+.*\.(py|js|json|txt|md|yml|yaml|toml|cfg|ini|log)',
            r'\b(create|write|make|generate|add)\s+.*\.(py|js|json|txt|md|yml|yaml|toml|cfg|ini)',
            r'\b(run|execute|start|launch)\s+.*\b(command|script|test|build|install)',
            r'\b(find|search|locate)\s+.*\b(file|pattern|function|class|variable)',
            r'\b(list|show|display)\s+.*\b(directory|folder|files)',
            r'\bwhat.*in.*\b(directory|folder)',
            r'\b(analyze|review|check|examine)\s+.*\b(code|file|project)',
            r'\brequirements?\.(txt|py)',
            r'\bpackage\.json',
            r'\bsetup\.py',
            r'\bwhat.*files',
            r'\binstalled.*requirements?',
            r'\bcurrent\s+directory'
        ]
        
        if any(re.search(pattern, user_lower, re.IGNORECASE) for pattern in tool_patterns):
            return True
        
        # Check AI response for suggestions that need tools
        response_lower = ai_response.lower()
        tool_suggestions = [
            "would need to",
            "let me check",
            "let me read",
            "let me look",
            "let me find",
            "let me list",
            "i'll check",
            "i'll read",
            "i'll look"
        ]
        
        return any(suggestion in response_lower for suggestion in tool_suggestions)
    
    def _parse_tools_from_response(self, response: str) -> List[ToolRequest]:
        """Parse tool requests directly from AI response if present"""
        try:
            # Look for JSON arrays in the response
            json_match = re.search(r'\[[\s\S]*?\]', response, re.DOTALL)
            if not json_match:
                return []
            
            tools_data = json.loads(json_match.group())
            if not isinstance(tools_data, list):
                return []
            
            requests = []
            for tool_data in tools_data:
                if isinstance(tool_data, dict) and 'tool' in tool_data:
                    requests.append(ToolRequest(
                        action=tool_data['tool'],
                        params=tool_data.get('args', {})
                    ))
            
            return requests
            
        except Exception as e:
            logger.debug(f"No tools found in response: {e}")
            return []
    
    def _extract_tool_requests(self, user_input: str, initial_response: str, messages: List[Dict]) -> List[ToolRequest]:
        """Extract tool requests using AI"""
        
        tool_prompt = f"""Based on this conversation, determine what tools should be used.

User request: {user_input}
Your initial response: {initial_response}

Available tools:
- read_file: Read file contents (args: path)
- write_file: Create new files (args: path, content)  
- edit_file: Edit existing files (args: path, action, content, match_text, start_line, end_line)
- run_command: Execute shell commands (args: cmd, timeout)
- find_files: Search for files (args: pattern, search_type, max_results)
- list_directory: List directory contents (args: path)

Respond with a JSON array of tool requests in this exact format:
[{{"tool": "tool_name", "args": {{"key": "value"}}}}]

If no tools are needed, respond with: []
"""
        
        try:
            tool_messages = messages + [{"role": "system", "content": tool_prompt}]
            print("[TOOLS] Analyzing what tools are needed...")
            response = call_llm(tool_messages)
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                print("[TOOLS] No tool requests found in AI response")
                return []
                
            tools_data = json.loads(json_match.group())
            
            requests = []
            for tool_data in tools_data:
                if isinstance(tool_data, dict) and 'tool' in tool_data:
                    requests.append(ToolRequest(
                        action=tool_data['tool'],
                        params=tool_data.get('args', {})
                    ))
            
            print(f"[TOOLS] Found {len(requests)} tool request(s)")
            return requests
            
        except Exception as e:
            logger.error(f"Failed to extract tool requests: {e}")
            print(f"[ERROR] Tool extraction failed: {str(e)}")
            # Fallback: Try to parse from the original response if it contains JSON
            if 'json' in str(e).lower() and '[' in initial_response and ']' in initial_response:
                print("[FALLBACK] Trying to parse tools from initial response...")
                try:
                    json_match = re.search(r'\[.*\]', initial_response, re.DOTALL)
                    if json_match:
                        tools_data = json.loads(json_match.group())
                        requests = []
                        for tool_data in tools_data:
                            if isinstance(tool_data, dict) and 'tool' in tool_data:
                                requests.append(ToolRequest(
                                    action=tool_data['tool'],
                                    params=tool_data.get('args', {})
                                ))
                        print(f"[FALLBACK] Found {len(requests)} tool request(s)")
                        return requests
                except Exception as fallback_error:
                    logger.error(f"Fallback parsing also failed: {fallback_error}")
            
            return []
    
    def _execute_tools_with_progress(self, tool_requests: List[ToolRequest]) -> List[ToolResult]:
        """Execute tools with progress indication and parallel processing"""
        
        if not tool_requests:
            return []
            
        print(f"[TOOLS] Executing {len(tool_requests)} tool(s)...")
        
        results = []
        
        # Determine which tools can run in parallel
        parallel_safe = ['read_file', 'find_files', 'list_directory']
        serial_tools = [req for req in tool_requests if req.action not in parallel_safe]
        parallel_tools = [req for req in tool_requests if req.action in parallel_safe]
        
        # Execute parallel-safe tools first
        if parallel_tools:
            with ThreadPoolExecutor(max_workers=min(len(parallel_tools), self.max_parallel)) as executor:
                future_to_request = {
                    executor.submit(self._execute_single_tool, req): req 
                    for req in parallel_tools
                }
                
                for future in as_completed(future_to_request, timeout=self.timeout_seconds):
                    try:
                        result = future.result()
                        results.append(result)
                        status = "SUCCESS" if result.success else "FAILED"
                        print(f"[TOOL] {result.request.action}: {status}")
                    except Exception as e:
                        req = future_to_request[future]
                        results.append(ToolResult(
                            request=req,
                            success=False,
                            error=f"Execution timeout or error: {str(e)}"
                        ))
        
        # Execute serial tools one by one
        for req in serial_tools:
            result = self._execute_single_tool(req)
            results.append(result)
            status = "SUCCESS" if result.success else "FAILED"
            print(f"[TOOL] {result.request.action}: {status}")
        
        return results
    
    def _execute_single_tool(self, request: ToolRequest) -> ToolResult:
        """Execute a single tool with caching and error handling"""
        
        start_time = time.time()
        
        # Check cache first
        cache_key = f"{request.action}_{hash(str(sorted(request.params.items())))}"
        if cache_key in self.cache:
            cached_result = self.cache[cache_key]
            cached_result.cached = True
            return cached_result
        
        try:
            # Get tool function from registry
            if request.action not in TOOL_REGISTRY:
                return ToolResult(
                    request=request,
                    success=False,
                    error=f"Unknown tool: {request.action}"
                )
            
            tool_func = TOOL_REGISTRY[request.action]
            
            # Execute tool
            result_data = tool_func(**request.params)
            
            result = ToolResult(
                request=request,
                success=True,
                result=result_data,
                execution_time=time.time() - start_time
            )
            
            # Cache successful results (for read operations only)
            if request.action in ['read_file', 'list_directory', 'find_files']:
                self.cache[cache_key] = result
                
            return result
            
        except Exception as e:
            return ToolResult(
                request=request,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _handle_tool_failures(self, context: ExecutionContext, messages: List[Dict]) -> Optional[List[ToolResult]]:
        """Handle tool failures with AI correction and retry"""
        
        if context.retry_count >= context.max_retries:
            return None
            
        context.retry_count += 1
        print(f"[RETRY] Attempting correction (attempt {context.retry_count}/{context.max_retries})...")
        
        # Build failure report
        failures = [r for r in context.results if not r.success]
        failure_report = "\n".join([
            f"Tool: {r.request.action}, Error: {r.error}" 
            for r in failures
        ])
        
        correction_prompt = f"""Some tools failed to execute. Please suggest corrections:

Original user request: {context.user_input}
Failed tools:
{failure_report}

Available tools:
- read_file: Read file contents (args: path)
- write_file: Create new files (args: path, content)  
- edit_file: Edit existing files (args: path, action, content, match_text, start_line, end_line)
- run_command: Execute shell commands (args: cmd, timeout)
- find_files: Search for files (args: pattern, search_type, max_results)
- list_directory: List directory contents (args: path)

Provide corrected tool requests as JSON array:
[{{"tool": "tool_name", "args": {{"key": "value"}}}}]

If no correction is possible, respond with: []
"""
        
        try:
            correction_messages = messages + [{"role": "system", "content": correction_prompt}]
            response = call_llm(correction_messages)
            
            # Extract corrected requests
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return None
                
            corrected_data = json.loads(json_match.group())
            corrected_requests = []
            
            for tool_data in corrected_data:
                if isinstance(tool_data, dict) and 'tool' in tool_data:
                    corrected_requests.append(ToolRequest(
                        action=tool_data['tool'],
                        params=tool_data.get('args', {})
                    ))
            
            if corrected_requests:
                # Execute corrected requests
                corrected_results = self._execute_tools_with_progress(corrected_requests)
                
                # Replace failed results with corrected ones
                final_results = []
                for original_result in context.results:
                    if original_result.success:
                        final_results.append(original_result)
                
                final_results.extend(corrected_results)
                return final_results
                
        except Exception as e:
            logger.error(f"Failed to handle tool failures: {e}")
            
        return None
    
    def _generate_summary(self, user_input: str, initial_response: str, results: List[ToolResult], messages: List[Dict]) -> str:
        """Generate final AI summary with tool results"""
        
        if not results:
            return initial_response
        
        # Format results for AI
        results_text = []
        for result in results:
            if result.success:
                status = "SUCCESS"
                if result.cached:
                    status += " (cached)"
                results_text.append(f"Tool: {result.request.action} - {status}")
                results_text.append(f"Result: {str(result.result)[:500]}...")  # Limit result size
            else:
                results_text.append(f"Tool: {result.request.action} - FAILED: {result.error}")
        
        summary_prompt = f"""Based on the tool execution results, provide a helpful response to the user.

User request: {user_input}
Your initial response: {initial_response}

Tool execution results:
{chr(10).join(results_text)}

Please provide a clear, helpful response that incorporates the tool results.
"""
        
        try:
            summary_messages = messages + [{"role": "system", "content": summary_prompt}]
            return call_llm_stream(summary_messages)
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return initial_response + f"\n\nTool execution completed with {len([r for r in results if r.success])} successful operations."

# Global instance
smart_tool_system = SmartToolSystem()