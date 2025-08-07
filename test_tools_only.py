#!/usr/bin/env python3

import sys
import time
from tracking.tracker import tracker
from database.connection import db_connection

def test_tools_only():
    """Test just the tool functionality and database tracking"""
    
    print("=== Testing Tools and Tracking ===")
    
    # Initialize database and start session
    try:
        db_connection.initialize_schema()
        session_id = tracker.start_session()
        print(f"[OK] Tracking session started: {session_id}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize tracking: {e}")
        return
    
    # Start an interaction
    try:
        interaction_id = tracker.start_interaction("Create addition function in test.py", 1)
        print(f"[OK] Started tracking interaction: {interaction_id}")
    except Exception as e:
        print(f"[ERROR] Failed to start interaction: {e}")
    
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
    
    # Test command execution
    print("\n--- Testing Command Execution ---")
    try:
        from tools.command_runner import run_command
        
        print("Running python test.py...")
        output = run_command("python test.py")
        print(f"[OK] Command output: {output}")
        
    except Exception as e:
        print(f"[ERROR] Error running command: {e}")
    
    # Complete the interaction
    try:
        from config import MODEL_NAME
        tracker.complete_interaction("Addition function created successfully", MODEL_NAME)
        print("[OK] Interaction tracking completed")
    except Exception as e:
        print(f"[ERROR] Failed to complete interaction: {e}")
    
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
            
            # Check command executions
            result = session.execute(text("SELECT COUNT(*) FROM command_executions")).scalar()
            print(f"[OK] Command executions in database: {result}")
            
    except Exception as e:
        print(f"[ERROR] Error checking database: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_tools_only()