import logging
import re
import json
import time
from llm.ollama_client import call_llm, call_llm_stream
from tools.tool_registry import TOOL_REGISTRY
from tracking.tracker import tracker
from database.connection import db_connection
from core.tool_validator import tool_validator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_tool_calls(response):
    """Parse and execute tool calls from AI response"""
    results = []
    
    # Find all tool calls in the response (handle multiple formats)
    # Format 1: TOOL_CALL: tool_name\nARGS: {...}
    # Format 2: TOOL_CALL: tool_name(...)\n{...}
    tool_pattern = r'TOOL_CALL:\s*(\w+)(?:\s*\([^)]*\))?\s*(?:\nARGS:\s*)?({[^}]*}|\{[\s\S]*?\})'
    matches = re.findall(tool_pattern, response, re.MULTILINE | re.DOTALL)
    
    for tool_name, args_str in matches:
        try:
            # Parse arguments
            args = json.loads(args_str)
            
            # Validate tool call before execution
            should_execute, block_reason = tool_validator.validate_tool_call(tool_name, args)
            
            if not should_execute:
                # Check for alternative suggestions
                suggestion = tool_validator.suggest_alternative(tool_name, args)
                if suggestion:
                    results.append(f"{tool_name}: {suggestion}")
                else:
                    results.append(f"{tool_name}: Skipped - {block_reason}")
                continue
            
            # Get tool function
            if tool_name in TOOL_REGISTRY:
                tool_func = TOOL_REGISTRY[tool_name]
                
                # Execute tool (log to system, don't print to chat)
                logger.info(f"Executing {tool_name} with args: {args}")
                
                # Measure execution time
                start_time = time.time()
                
                # Handle both named parameters and positional arg1, arg2, etc.
                if tool_name == "read_file":
                    path = args.get("path") or args.get("arg1") or args.get("arg")
                    if path:
                        result = tool_func(path)
                    else:
                        result = "Error: Missing 'path' parameter"
                        
                elif tool_name == "write_file":
                    path = args.get("path") or args.get("arg1") 
                    edits = args.get("edits") or args.get("arg2")
                    if path and edits:
                        result = tool_func(path, edits)
                    else:
                        result = "Error: Missing 'path' or 'edits' parameter"
                        
                elif tool_name == "run_command":
                    cmd = args.get("cmd") or args.get("arg1") or args.get("arg")
                    if cmd:
                        result = tool_func(cmd)
                    else:
                        result = "Error: Missing 'cmd' parameter"
                        
                elif tool_name == "find_files":
                    pattern = args.get("pattern") or args.get("arg1") or args.get("arg", "*")
                    search_type = args.get("search_type") or args.get("arg2", "name")
                    max_results = args.get("max_results") or args.get("arg3", 100)
                    result = tool_func(pattern, search_type, max_results)
                    
                elif tool_name == "list_directory":
                    path = args.get("path") or args.get("arg1") or args.get("arg", ".")
                    result = tool_func(path)
                    
                else:
                    result = f"Unknown tool: {tool_name}"
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Record successful tool call for context tracking
                tool_validator.record_tool_call(tool_name, args, result, execution_time)
                
                # Track tool call in database
                try:
                    execution_time_ms = int(execution_time * 1000)  # Convert to milliseconds
                    tracker.track_tool_call(tool_name, args, result, execution_time_ms)
                except Exception as e:
                    logger.error(f"Failed to track tool call: {e}")
                
                results.append(f"{tool_name}: {result}")
                
            else:
                results.append(f"Error: Tool '{tool_name}' not found")
                
        except json.JSONDecodeError as e:
            results.append(f"Error parsing args for {tool_name}: {e}")
        except Exception as e:
            results.append(f"Error executing {tool_name}: {e}")
    
    return "\n".join(results) if results else None

def start_repl():
    print("Clokai: Initializing database...")
    
    # Initialize database and start session
    try:
        db_connection.initialize_schema()
        session_id = tracker.start_session()
        print(f"Clokai: Tracking session started: {session_id}")
    except Exception as e:
        logger.error(f"Failed to initialize tracking: {e}")
        print("Clokai: Running without tracking (database unavailable)")
    
    # Enhanced system prompt with tool capabilities
    system_prompt = """You are a helpful local coding assistant with access to tools. You are working in the current project directory with full recursive access to all subdirectories.

Available tools:
1. read_file(path) - Read contents of a file (supports full paths like "core/editor.py")
2. write_file(path, edits) - Write or edit files (supports both simple string content or structured edits)
3. run_command(cmd) - Execute shell commands
4. find_files(pattern, search_type, max_results) - Search for files in the entire project
   - search_type: "name" (filename search), "glob" (pattern matching), "regex", "content" (search inside files)
   - Examples: find_files("editor", "name") or find_files("*.py", "glob") or find_files("class.*Editor", "regex")
5. list_directory(path) - List contents of a directory

When you need to use a tool, respond in this format:
TOOL_CALL: tool_name
ARGS: {"arg1": "value1", "arg2": "value2"}

Examples:
TOOL_CALL: find_files
ARGS: {"pattern": "editor", "search_type": "name"}

TOOL_CALL: read_file
ARGS: {"path": "core/editor.py"}

TOOL_CALL: find_files
ARGS: {"pattern": "*.py", "search_type": "glob", "max_results": 50}

TOOL_CALL: write_file
ARGS: {"path": "core/utils.py", "edits": "def helper_function():\n    return 'Hello World'"}

IMPORTANT BEHAVIOR:
- When users ask about files that might not be in the root directory, ALWAYS use find_files first to locate them
- If you can't find a file in the root directory, search for it using find_files before giving up
- Use find_files with different search types: "name" for partial filename matches, "glob" for patterns, "content" for searching inside files
- Always search recursively through the entire project structure
- Be proactive with file searching - if unsure about file location, search first
- After finding files, use read_file with the full path to read them
- If a tool execution fails with an error, analyze the error message and try alternative approaches
- For command errors, suggest corrected commands or alternative solutions
- Always provide helpful responses even when tools fail - explain what went wrong and offer alternatives
- Explain what you're doing, then make the tool call"""

    messages = [{"role": "system", "content": system_prompt}]
    print("Clokai: Local Claude-style CLI is running. Type '/exit' to quit.")
    
    interaction_count = 0

    while True:
        user_input = input("You: ")
        if user_input.strip() == "/exit":
            break
        if user_input.startswith("/"):
            if user_input == "/tool_report":
                from core.tool_monitor import tool_monitor
                validation_report = tool_monitor.get_validation_report()
                performance_report = tool_monitor.get_performance_report()
                
                print("\n=== TOOL VALIDATION REPORT ===")
                print(f"Total tool calls: {validation_report['total_tool_calls']}")
                print(f"Blocked calls: {validation_report['blocked_calls']}")
                print(f"Success rate: {validation_report['success_rate']:.1f}%")
                print("\nBlock breakdown:")
                for block_type, count in validation_report['block_breakdown'].items():
                    print(f"  {block_type}: {count}")
                
                if validation_report['recent_blocked_calls']:
                    print("\nRecent blocked calls:")
                    for call in validation_report['recent_blocked_calls']:
                        print(f"  [{call['timestamp']}] {call['tool_name']}: {call['reason']}")
                
                print("\n=== PERFORMANCE REPORT ===")
                for tool_name, stats in performance_report.items():
                    print(f"{tool_name}: {stats['call_count']} calls, avg {stats['avg_execution_time']:.3f}s")
                
                continue
            elif user_input == "/help":
                print("\nAvailable commands:")
                print("  /tool_report - Show tool validation and performance report")
                print("  /help - Show this help message")
                print("  /exit - Exit the CLI")
                continue
            else:
                print("Command not implemented yet. Type /help for available commands.")
                continue

        interaction_count += 1
        
        # Reset tool validator context for new user input
        tool_validator.reset_context()
        
        # Start tracking the interaction
        try:
            tracker.start_interaction(user_input, interaction_count)
        except Exception as e:
            logger.error(f"Failed to start tracking interaction: {e}")

        messages.append({"role": "user", "content": user_input})
        
        try:
            # Use streaming for initial response
            response = call_llm_stream(messages)
            
            # Handle tool calls in a loop to support multiple rounds
            current_response = response
            all_responses = [response]
            
            while "TOOL_CALL:" in current_response:
                messages.append({"role": "assistant", "content": current_response})
                
                # Execute tool calls
                tool_results = execute_tool_calls(current_response)
                
                if tool_results:
                    # Add tool results to conversation (log only, don't print)
                    tool_result_msg = f"Tool execution results:\n{tool_results}"
                    logger.info(f"Tool results: {tool_results}")
                    messages.append({"role": "system", "content": tool_result_msg})
                    
                    # Get follow-up response from AI (streaming)
                    follow_up = call_llm_stream(messages)
                    all_responses.append(follow_up)
                    current_response = follow_up
                else:
                    break
            
            # Add final response to messages
            messages.append({"role": "assistant", "content": current_response})
            final_response = "\n\n".join(all_responses)
            
            # Complete tracking the interaction
            try:
                from config import MODEL_NAME
                tracker.complete_interaction(final_response, MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to complete tracking interaction: {e}")
                
        except Exception as e:
            error_msg = f"Error calling LLM: {e}"
            print("Clokai:", error_msg)
            
            # Track the error
            try:
                from config import MODEL_NAME
                tracker.complete_interaction("", MODEL_NAME, error_message=str(e))
            except Exception as track_error:
                logger.error(f"Failed to track error: {track_error}")
    
    print("Clokai: Session ended.")