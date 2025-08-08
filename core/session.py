import logging
import time
from llm.ollama_client import call_llm, call_llm_stream
from tracking.tracker import tracker
from database.connection import db_connection
from core.rich_cli import rich_cli
from core.smart_tool_system import smart_tool_system
from core.claude_tool_system import claude_tool_system, ToolCall

# Setup logging - reduce noise in CLI
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Set specific loggers to be quieter
logging.getLogger('database.connection').setLevel(logging.ERROR)
logging.getLogger('tracking.tracker').setLevel(logging.ERROR)

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
- When you need to perform actions like reading files, running commands, or searching, the system will automatically handle tool execution
- Focus on being helpful and providing clear explanations
- Be direct and concise in your responses

AVAILABLE TOOLS (automatically handled):
- read_file: Read file contents
- write_file: Create new files  
- edit_file: Edit existing files
- run_command: Execute shell commands
- find_files: Search for files
- list_directory: List directory contents

You don't need to explicitly call tools - just respond naturally and the system will handle tool execution when needed."""

    messages = [{"role": "system", "content": system_prompt}]
    interaction_count = 0

    while True:
        user_input = rich_cli.show_user_input()
        if user_input.strip() == "/exit":
            break
            
        # Handle CLI commands
        if user_input.startswith("/"):
            if user_input == "/help":
                rich_cli.show_help()
                continue
            elif user_input == "/status":
                from config import MODEL_NAME
                rich_cli.show_status(MODEL_NAME, session_id)
                continue
            elif user_input == "/clear":
                # Clear conversation history
                messages = [{"role": "system", "content": system_prompt}]
                rich_cli.console.print("[dim]Conversation history cleared.[/dim]")
                continue
            else:
                rich_cli.show_error(f"Unknown command: {user_input}. Type /help for available commands.")
                continue

        interaction_count += 1
        
        # Start tracking the interaction
        try:
            tracker.start_interaction(user_input, interaction_count)
        except Exception as e:
            logger.error(f"Failed to start tracking interaction: {e}")

        messages.append({"role": "user", "content": user_input})
        
        try:
            # Use the smart tool system for processing
            print("[PROCESSING] Analyzing your request...")
            
            initial_response, tool_requests = smart_tool_system.process_user_request(user_input, messages)
            
            tool_results = None
            if tool_requests:
                tool_calls = [ToolCall(name=req.request.action, args=req.request.params) for req in tool_requests]
                tool_results = claude_tool_system.execute_tools_parallel(tool_calls)

            # Generate final response
            final_response = smart_tool_system._generate_summary(user_input, initial_response, tool_results, messages)

            # Add the final response to conversation history
            messages.append({"role": "assistant", "content": final_response})
            
            # Display the response
            rich_cli.console.print(f"\n[bold green]Clokai[/bold green]: {final_response}")
            
            # Complete tracking the interaction
            try:
                from config import MODEL_NAME
                tracker.complete_interaction(final_response, MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to complete tracking interaction: {e}")
                
        except Exception as e:
            error_msg = f"Error processing request: {e}"
            rich_cli.show_error(error_msg)
            # Track the error
            try:
                from config import MODEL_NAME
                tracker.complete_interaction("", MODEL_NAME, error_message=str(e))
            except Exception as track_error:
                logger.error(f"Failed to track error: {track_error}")
    
    rich_cli.console.print("\n[bold green]Thanks for using Clokai! Session ended.[/bold green]")


