import logging
import re
import json
import time
from llm.ollama_client import call_llm, call_llm_stream
from tools.tool_registry import TOOL_REGISTRY
from tracking.tracker import tracker
from database.connection import db_connection
from core.tool_validator import tool_validator
from core.claude_tool_system import claude_tool_system
from core.rich_cli import rich_cli
from core.intent_detector import intent_detector
from core.tool_protocol import tool_protocol

# Setup logging - reduce noise in CLI
logging.basicConfig(level=logging.WARNING)  # Changed from INFO to WARNING
logger = logging.getLogger(__name__)

# Set specific loggers to be quieter
logging.getLogger('database.connection').setLevel(logging.ERROR)
logging.getLogger('tracking.tracker').setLevel(logging.ERROR)
logging.getLogger('core.tool_validator').setLevel(logging.ERROR)
logging.getLogger('core.tool_monitor').setLevel(logging.ERROR)

def execute_tool_calls(response):
    """
    Parse and execute tool calls from AI response using the advanced Claude tool system.
    This provides parallel execution, better error handling, and structured results.
    """
    # Parse tool calls using the advanced system
    tool_calls = claude_tool_system.parse_tool_calls(response)
    
    if not tool_calls:
        return None
    
    # Execute tools with parallel processing and dependency management
    results = claude_tool_system.execute_tools_parallel(tool_calls)
    
    # Track results in database
    for result in results:
        try:
            execution_time_ms = int(result.execution_time * 1000)
            status = "success" if result.success else "error"
            error_message = result.error if not result.success else None
            
            tracker.track_tool_call(
                result.tool_call.name, 
                result.tool_call.args, 
                str(result.result) if result.result else "", 
                execution_time_ms,
                status=status,
                error_message=error_message
            )
        except Exception as e:
            logger.error(f"Failed to track tool call: {e}")
    
    # Format results for display
    formatted_results = claude_tool_system.format_tool_results(results)
    
    return formatted_results if formatted_results else None

def start_repl():
    # Initialize database and start session
    try:
        db_connection.initialize_schema()
        session_id = tracker.start_session()
        rich_cli.show_welcome(session_id)
    except Exception as e:
        logger.error(f"Failed to initialize tracking: {e}")
        session_id = "offline"
        rich_cli.show_welcome(session_id)
    
    # Load system prompt from file
    try:
        with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
            system_prompt = f.read().strip()
    except FileNotFoundError:
        # Fallback system prompt if file not found
        system_prompt = """You are a local AI coding assistant operating in HYBRID MODE. You work entirely offline and within the current project directory only.

CRITICAL RULES FOR HYBRID MODE:
- Use natural language for communication, reasoning, and explanations
- NEVER write file-changing code directly into your natural language response
- ONLY use the `edit_file` tool for modifying existing files
- ONLY use the `write_file` tool for creating new files (never for editing existing ones)
- You may explain your reasoning first, but all code changes must be submitted via tool calls
- Always return tool calls in structured JSON format

AVAILABLE TOOLS:
- read_file: Read file contents
- edit_file: Surgically edit existing files (insert_before, insert_after, replace_range, append_to_end)
- write_file: Create new files only
- run_command: Execute shell commands
- find_files: Search for files
- list_directory: List directory contents

When editing files, prefer surgical edits using edit_file over full rewrites. This ensures safer, more precise modifications that are easier to track and revert."""

    messages = [{"role": "system", "content": system_prompt}]
    
    interaction_count = 0

    while True:
        user_input = rich_cli.show_user_input()
        if user_input.strip() == "/exit":
            break
        if user_input.startswith("/"):
            if user_input == "/tool_report":
                from core.tool_monitor import tool_monitor
                validation_report = tool_monitor.get_validation_report()
                performance_report = tool_monitor.get_performance_report()
                rich_cli.show_tool_report(validation_report, performance_report)
                continue
            elif user_input == "/help":
                rich_cli.show_help()
                continue
            elif user_input == "/status":
                from config import MODEL_NAME
                rich_cli.show_status(MODEL_NAME, session_id)
                continue
            else:
                rich_cli.show_error(f"Unknown command: {user_input}. Type /help for available commands.")
                continue

        interaction_count += 1
        
        # Reset conversation context for new user input
        claude_tool_system.reset_conversation_context()
        
        # Start tracking the interaction
        try:
            tracker.start_interaction(user_input, interaction_count)
        except Exception as e:
            logger.error(f"Failed to start tracking interaction: {e}")

        messages.append({"role": "user", "content": user_input})
        
        try:
            # Step 1: Ask AI if this message needs tools
            intent_analysis = intent_detector.analyze_intent(user_input)
            
            # Show intent reasoning with special indicators
            if intent_analysis.force_tools:
                rich_cli.console.print(f"[dim][FORCE] {intent_analysis.reasoning}[/dim]")
            elif intent_analysis.suggested_retry:
                rich_cli.console.print(f"[dim][RETRY] {intent_analysis.reasoning}[/dim]")
            else:
                rich_cli.console.print(f"[dim][INTENT] {intent_analysis.reasoning}[/dim]")
            
            if intent_analysis.needs_tools:
                # Step 2: Send available tools to AI and let it proceed
                all_available_tools = [
                    "- read_file: Read file contents (args: file_path)",
                    "- write_file: Create new files (args: file_path, content)", 
                    "- edit_file: Edit existing files (args: file_path, edit_type, content, line_number)",
                    "- run_command: Execute shell commands (args: command, timeout)",
                    "- find_files: Search for files (args: pattern, directory)",
                    "- list_directory: List directory contents (args: directory)"
                ]
                
                tools_list = chr(10).join(all_available_tools)
                tools_prompt = (f"Available tools:\n{tools_list}\n\n"
                              f"User request: {user_input}\n\n"
                              f"Respond naturally and use tools if needed.")
                
                messages.append({"role": "system", "content": tools_prompt})
                
                # Get AI response with tools
                response = call_llm_stream(messages)
                messages.append({"role": "assistant", "content": response})
                
                # Check if AI used tools and execute them
                tool_calls = claude_tool_system.parse_tool_calls(response)
                
                if tool_calls:
                    tool_call_dicts = [{"name": tc.name, "args": tc.args} for tc in tool_calls]
                    rich_cli.show_tool_execution(tool_call_dicts)
                    
                    tool_results = execute_tool_calls(response)
                    
                    if tool_results:
                        rich_cli.show_tool_results(tool_results)
                        
                        # Generate summary
                        tool_responses = [(tc.name, "success") for tc in tool_calls]
                        summary = tool_protocol.generate_summary(tool_responses)
                        rich_cli.console.print(f"[dim]Summary: {summary}[/dim]")
                        
                        # Add results and get follow-up
                        tool_result_msg = f"Tool execution completed:\n{tool_results}"
                        messages.append({"role": "system", "content": tool_result_msg})
                        
                        follow_up = call_llm_stream(messages)
                        messages.append({"role": "assistant", "content": follow_up}")
                        
                        final_response = f"{response}\n\n{follow_up}"
                    else:
                        final_response = response
                else:
                    # AI didn't use tools but we expected it to - trigger fallback
                    if intent_analysis.suggested_retry or intent_analysis.force_tools:
                        rich_cli.console.print("[dim]Retrying with tool context since no action was taken.[/dim]")
                        
                        # Force retry with more explicit tool instruction
                        tools_list = chr(10).join(all_available_tools)
                        retry_prompt = (f"The user's request likely needs tools but you didn't use any. "
                                      f"Please reconsider and use appropriate tools.\n\n"
                                      f"Available tools:\n{tools_list}\n\n"
                                      f"Original user request: {user_input}\n"
                                      f"Your previous response: {response}\n\n"
                                      f"Now please provide a better response using tools if needed.")
                        
                        messages.append({"role": "system", "content": retry_prompt})
                        retry_response = call_llm_stream(messages)
                        messages.append({"role": "assistant", "content": retry_response})
                        
                        # Try to execute tools from retry
                        retry_tool_calls = claude_tool_system.parse_tool_calls(retry_response)
                        if retry_tool_calls:
                            tool_call_dicts = [{"name": tc.name, "args": tc.args} for tc in retry_tool_calls]
                            rich_cli.show_tool_execution(tool_call_dicts)
                            
                            tool_results = execute_tool_calls(retry_response)
                            if tool_results:
                                rich_cli.show_tool_results(tool_results)
                                final_response = f"{response}\n\n{retry_response}"
                            else:
                                final_response = f"{response}\n\n{retry_response}"
                        else:
                            final_response = f"{response}\n\n{retry_response}"
                    else:
                        final_response = response
            else:
                # No tools needed, normal AI response
                response = call_llm_stream(messages)
                messages.append({"role": "assistant", "content": response})
                
                # Check if we should suggest retry based on response content
                should_retry = intent_detector.suggest_retry_with_tools(user_input, response)
                if should_retry:
                    rich_cli.console.print("[dim]Response suggests tools might be helpful. Retrying with tool context.[/dim]")
                    
                    all_available_tools = [
                        "- read_file: Read file contents (args: file_path)",
                        "- write_file: Create new files (args: file_path, content)", 
                        "- edit_file: Edit existing files (args: file_path, edit_type, content, line_number)",
                        "- run_command: Execute shell commands (args: command, timeout)",
                        "- find_files: Search for files (args: pattern, directory)",
                        "- list_directory: List directory contents (args: directory)"
                    ]
                    
                    tools_list = chr(10).join(all_available_tools)
                    tools_prompt = (f"Available tools:\n{tools_list}\n\n"
                                  f"The user's original request was: {user_input}\n\n"
                                  f"Your previous response suggested actions that could benefit from using tools. "
                                  f"Please use tools to provide a more helpful response.")
                    
                    messages.append({"role": "system", "content": tools_prompt})
                    retry_response = call_llm_stream(messages)
                    messages.append({"role": "assistant", "content": retry_response})
                    
                    # Try to execute tools from retry
                    retry_tool_calls = claude_tool_system.parse_tool_calls(retry_response)
                    if retry_tool_calls:
                        tool_call_dicts = [{"name": tc.name, "args": tc.args} for tc in retry_tool_calls]
                        rich_cli.show_tool_execution(tool_call_dicts)
                        
                        tool_results = execute_tool_calls(retry_response)
                        if tool_results:
                            rich_cli.show_tool_results(tool_results)
                        final_response = f"{response}\n\n{retry_response}"
                    else:
                        final_response = response
                else:
                    final_response = response
            
            # Complete tracking the interaction
            try:
                from config import MODEL_NAME
                tracker.complete_interaction(final_response, MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to complete tracking interaction: {e}")
                
        except Exception as e:
            error_msg = f"Error calling LLM: {e}"
            rich_cli.show_error(error_msg)
            
            # Track the error
            try:
                from config import MODEL_NAME
                tracker.complete_interaction("", MODEL_NAME, error_message=str(e))
            except Exception as track_error:
                logger.error(f"Failed to track error: {track_error}")
    
    rich_cli.console.print("\n[bold green]Thanks for using Clokai! Session ended.[/bold green]")