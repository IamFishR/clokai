import requests
import json
import re
import logging
import sys
import time

from config import OLLAMA_API_URL, MODEL_NAME

logger = logging.getLogger(__name__)

def clean_response(response):
    """Clean AI response by removing thinking tags and other unwanted patterns"""
    if not response:
        return response
    
    # Remove <think>...</think> blocks (including multiline)
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove any standalone thinking markers
    response = re.sub(r'</?think>', '', response, flags=re.IGNORECASE)
    
    # Remove excessive whitespace and newlines
    response = re.sub(r'\n\s*\n\s*\n', '\n\n', response)  # Max 2 consecutive newlines
    response = response.strip()
    
    return response

def count_tokens(text):
    """Simple token counting - approximates tokens as words * 1.3"""
    if not text:
        return 0
    # Rough approximation: split by spaces and multiply by 1.3
    return int(len(text.split()) * 1.3)

def call_llm(messages, max_retries=2, call_type="main", call_sequence=1):
    """Call Ollama LLM with response cleaning and error handling"""
    
    # Extract system prompt for tracking
    system_prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
            break
    
    # Convert messages to prompt for Ollama API
    prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            prompt += f"System: {msg['content']}\n"
        elif msg["role"] == "user":
            prompt += f"User: {msg['content']}\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['content']}\n"
    
    prompt += "Assistant: "
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                timeout=60  # 60 second timeout
            )
            response.raise_for_status()
            
            raw_response = response.json()["response"]
            cleaned_response = clean_response(raw_response)
            
            # Check if response is empty or too short after cleaning
            if not cleaned_response or len(cleaned_response.strip()) < 5:
                if attempt < max_retries:
                    logger.warning(f"Empty response on attempt {attempt + 1}, retrying...")
                    continue
                else:
                    return "I apologize, but I'm having trouble generating a proper response. Please try again.", count_tokens(prompt), 0
            
            # Count tokens for tracking
            input_tokens = count_tokens(prompt)
            output_tokens = count_tokens(cleaned_response)
            
            # Track the LLM call
            try:
                from tracking.tracker import tracker
                if tracker.current_interaction_id:  # Only track if there's an active interaction
                    processing_time_ms = 0  # Will be calculated properly in smart_tool_system
                    tracker.track_llm_call(
                        call_type=call_type,
                        full_prompt=prompt,
                        system_prompt=system_prompt,
                        conversation_context=messages,
                        llm_response=cleaned_response,
                        model_used=MODEL_NAME,
                        processing_time_ms=processing_time_ms,
                        token_count_input=input_tokens,
                        token_count_output=output_tokens,
                        call_sequence=call_sequence
                    )
            except Exception as e:
                # Don't fail if tracking fails
                pass
            
            return cleaned_response, input_tokens, output_tokens
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logger.warning(f"Request timeout on attempt {attempt + 1}, retrying...")
                continue
            else:
                return "Request timed out. The model may be overloaded. Please try again.", count_tokens(prompt), 0
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                logger.warning(f"Request error on attempt {attempt + 1}: {e}, retrying...")
                continue
            else:
                return f"Error connecting to model: {e}", count_tokens(prompt), 0
                
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Unexpected error occurred: {e}", count_tokens(prompt), 0
    
    return "Failed to get response after multiple attempts.", count_tokens(prompt), 0

def call_llm_stream(messages, max_retries=2, call_type="main", call_sequence=1):
    """Call Ollama LLM with streaming response"""
    
    # Extract system prompt for tracking
    system_prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
            break
    
    # Convert messages to prompt for Ollama API
    prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            prompt += f"System: {msg['content']}\n"
        elif msg["role"] == "user":
            prompt += f"User: {msg['content']}\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['content']}\n"
    
    prompt += "Assistant: "
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": True,  # Enable streaming
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                timeout=60,
                stream=True  # Enable streaming in requests
            )
            response.raise_for_status()
            
            full_response = ""
            # Import here to avoid circular import
            from core.rich_cli import rich_cli
            rich_cli.show_ai_response_start()
            display_buffer = ""
            in_think_block = False
            
            # Process streaming response
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if 'response' in chunk:
                            token = chunk['response']
                            full_response += token
                            display_buffer += token
                            
                            # Real-time filtering for display
                            while True:
                                if not in_think_block and '<think>' in display_buffer:
                                    # Found start of think block
                                    before_think = display_buffer[:display_buffer.index('<think>')]
                                    rich_cli.stream_ai_response(before_think)
                                    display_buffer = display_buffer[display_buffer.index('<think>'):]
                                    in_think_block = True
                                elif in_think_block and '</think>' in display_buffer:
                                    # Found end of think block
                                    display_buffer = display_buffer[display_buffer.index('</think>') + 8:]
                                    in_think_block = False
                                else:
                                    # No think tags, print if not in think block
                                    if not in_think_block:
                                        rich_cli.stream_ai_response(display_buffer)
                                        display_buffer = ""
                                    break
                        
                        if chunk.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            # Print any remaining buffer (if not in think block)
            if not in_think_block and display_buffer:
                rich_cli.stream_ai_response(display_buffer)
            
            rich_cli.show_ai_response_end()  # New line after streaming
            
            # Clean the full response
            cleaned_response = clean_response(full_response)
            
            # Check if response is empty or too short after cleaning
            if not cleaned_response or len(cleaned_response.strip()) < 5:
                if attempt < max_retries:
                    logger.warning(f"Empty response on attempt {attempt + 1}, retrying...")
                    continue
                else:
                    return "I apologize, but I'm having trouble generating a proper response. Please try again.", count_tokens(prompt), 0
            
            # Count tokens for tracking
            input_tokens = count_tokens(prompt)
            output_tokens = count_tokens(cleaned_response)
            
            # Track the LLM call
            try:
                from tracking.tracker import tracker
                if tracker.current_interaction_id:  # Only track if there's an active interaction
                    processing_time_ms = 0  # Will be calculated properly in smart_tool_system
                    tracker.track_llm_call(
                        call_type=call_type,
                        full_prompt=prompt,
                        system_prompt=system_prompt,
                        conversation_context=messages,
                        llm_response=cleaned_response,
                        model_used=MODEL_NAME,
                        processing_time_ms=processing_time_ms,
                        token_count_input=input_tokens,
                        token_count_output=output_tokens,
                        call_sequence=call_sequence
                    )
            except Exception as e:
                # Don't fail if tracking fails
                pass
            
            return cleaned_response, input_tokens, output_tokens
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logger.warning(f"Request timeout on attempt {attempt + 1}, retrying...")
                continue
            else:
                return "Request timed out. The model may be overloaded. Please try again.", count_tokens(prompt), 0
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                logger.warning(f"Request error on attempt {attempt + 1}: {e}, retrying...")
                continue
            else:
                return f"Error connecting to model: {e}", count_tokens(prompt), 0
                
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Unexpected error occurred: {e}", count_tokens(prompt), 0
    
    return "Failed to get response after multiple attempts.", count_tokens(prompt), 0