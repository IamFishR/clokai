import logging
import time
from llm.ollama_client import call_llm, call_llm_stream

def _calculate_response_quality(response: str, user_input: str, tool_results) -> float:
    """Calculate response quality score based on multiple factors"""
    try:
        score = 0.0
        
        # Base score for having a response
        if response and len(response.strip()) > 10:
            score += 0.3
        
        # Length factor (reasonable length responses are better)
        response_length = len(response)
        if 50 <= response_length <= 1000:
            score += 0.2
        elif response_length > 1000:
            score += 0.1
        
        # Tool usage factor (successful tool usage indicates helpfulness)
        if tool_results:
            successful_tools = sum(1 for result in tool_results if result.success)
            tool_success_rate = successful_tools / len(tool_results)
            score += 0.3 * tool_success_rate
        
        # Error indicators (reduce score for obvious errors)
        error_indicators = ['error', 'failed', 'unable', 'cannot', 'sorry']
        error_count = sum(1 for indicator in error_indicators if indicator.lower() in response.lower())
        score -= min(0.2, error_count * 0.05)
        
        # Relevance factor (simple keyword matching)
        user_words = set(user_input.lower().split())
        response_words = set(response.lower().split())
        common_words = user_words.intersection(response_words)
        relevance_score = min(0.2, len(common_words) * 0.02)
        score += relevance_score
        
        return max(0.0, min(1.0, score))
        
    except Exception:
        return 0.5  # Default neutral score if calculation fails

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
            # Reset token counts for this interaction
            smart_tool_system.reset_session_token_counts()
            
            # Use the smart tool system for processing
            print("[PROCESSING] Analyzing your request...")
            
            final_response, tool_results = smart_tool_system.process_user_request(user_input, messages)

            # Add the final response to conversation history
            messages.append({"role": "assistant", "content": final_response})
            
            # Display the response
            rich_cli.console.print(f"\n[bold green]Clokai[/bold green]: {final_response}")
            
            # Complete tracking the interaction with token counts
            try:
                from config import MODEL_NAME
                input_tokens, output_tokens = smart_tool_system.get_session_token_counts()
                
                # Ensure final_response is a string, not a tuple
                if isinstance(final_response, tuple):
                    logger.error(f"final_response is unexpectedly a tuple: {final_response}")
                    final_response = str(final_response[0]) if len(final_response) > 0 else "Error: Empty response"
                
                # Calculate metrics before completing interaction
                processing_time = time.time() - tracker.interaction_start_time if tracker.interaction_start_time else 1
                tokens_per_sec = output_tokens / max(1, processing_time)
                
                # Improved response quality scoring
                quality_score = _calculate_response_quality(final_response, user_input, tool_results)
                tool_count = len(tool_results)
                
                tracker.complete_interaction(
                    final_response, 
                    MODEL_NAME, 
                    token_count_input=input_tokens,
                    token_count_output=output_tokens
                )
                
                # Track AI metrics (only if interaction was successfully completed)
                if not tracker.interaction_completed:
                    logger.warning("Interaction completion failed, skipping metrics")
                else:
                    tracker.track_ai_metric("tokens_per_second", tokens_per_sec, "tokens/sec")
                    tracker.track_ai_metric("response_quality_score", quality_score, "score")  
                    tracker.track_ai_metric("tool_usage_count", tool_count, "count")
            except Exception as e:
                import traceback
                logger.error(f"Failed to complete tracking interaction: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
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


