#!/usr/bin/env python3

import sys
import time
from core.session import start_repl
from llm.ollama_client import call_llm
from tracking.tracker import tracker
from database.connection import db_connection

def test_cli_functionality():
    """Test the CLI functionality programmatically"""
    
    print("=== Testing Clokai CLI with Tracking ===")
    
    # Initialize database and start session
    try:
        db_connection.initialize_schema()
        session_id = tracker.start_session()
        print(f"[OK] Tracking session started: {session_id}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize tracking: {e}")
        return
    
    # Test interaction
    try:
        print("\n--- Testing LLM Interaction ---")
        
        # Start tracking interaction
        user_prompt = "Create a simple Python function called 'add_numbers' that takes two parameters (a, b) and returns their sum. Put this in test.py file."
        interaction_id = tracker.start_interaction(user_prompt, 1)
        print(f"[OK] Started tracking interaction: {interaction_id}")
        
        # Call LLM
        messages = [
            {"role": "system", "content": "You are a helpful local coding assistant. You can read files, edit them surgically, and run shell commands."},
            {"role": "user", "content": user_prompt}
        ]
        
        print("Calling LLM...")
        response = call_llm(messages)
        print(f"[OK] LLM Response: {response[:100]}...")
        
        # Complete tracking
        from config import MODEL_NAME
        tracker.complete_interaction(response, MODEL_NAME)
        print("[OK] Interaction tracking completed")
        
    except Exception as e:
        print(f"[ERROR] Error during interaction: {e}")
        from config import MODEL_NAME
        tracker.complete_interaction("", MODEL_NAME, error_message=str(e))
    
    # Test tool functionality manually
    print("\n--- Testing Tool Functionality ---")
    
    try:
        from tools.file_ops import read_file, write_file
        
        # Read current test.py content
        print("Reading test.py...")
        content = read_file("test.py")
        print(f"[OK] Current content: {repr(content[:50])}")
        
        # Write addition function
        print("Writing addition function...")
        edits = [{
            "start_line": 0,
            "end_line": len(content.splitlines()) if content.strip() else 0,
            "replacement": [
                "def add_numbers(a, b):",
                "    \"\"\"Add two numbers and return the result\"\"\"",
                "    return a + b",
                "",
                "# Test the function",
                "if __name__ == '__main__':",
                "    result = add_numbers(5, 3)",
                "    print(f'5 + 3 = {result}')"
            ]
        }]
        
        result = write_file("test.py", edits)
        print(f"[OK] Write result: {result}")
        
        # Read updated content
        updated_content = read_file("test.py")
        print(f"[OK] Updated content preview: {updated_content[:100]}...")
        
    except Exception as e:
        print(f"[ERROR] Error during tool testing: {e}")
    
    # Check database tracking
    print("\n--- Checking Database Tracking ---")
    try:
        with db_connection.get_session() as session:
            from sqlalchemy import text
            
            # Check sessions
            result = session.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
            print(f"[OK] Sessions in database: {result}")
            
            # Check interactions
            result = session.execute(text("SELECT COUNT(*) FROM interactions")).scalar()
            print(f"[OK] Interactions in database: {result}")
            
            # Check tool calls
            result = session.execute(text("SELECT COUNT(*) FROM tool_calls")).scalar()
            print(f"[OK] Tool calls in database: {result}")
            
            # Check file snapshots
            result = session.execute(text("SELECT COUNT(*) FROM file_snapshots")).scalar()
            print(f"[OK] File snapshots in database: {result}")
            
    except Exception as e:
        print(f"[ERROR] Error checking database: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_cli_functionality()