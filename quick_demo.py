#!/usr/bin/env python3
"""
Quick demo of the beautiful CLI in action
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.rich_cli import rich_cli
from core.session import execute_tool_calls

def demo_cli():
    """Demonstrate the beautiful CLI interface"""
    
    # Show welcome
    rich_cli.show_welcome("demo-session-abc123")
    
    # Simulate a user request and AI response with tools
    print("\nUser: Can you read my test.py file and add a comment to it?")
    
    rich_cli.show_ai_response_start()
    rich_cli.stream_ai_response("I'll read your test.py file and add a helpful comment. Let me do this for you:")
    rich_cli.show_ai_response_end()
    
    # Show tool execution
    tool_calls = [
        {"name": "read_file", "args": {"path": "test.py"}},
        {"name": "edit_file", "args": {"path": "test.py", "action": "insert_before", "content": "# Enhanced system info script", "start_line": 1}}
    ]
    rich_cli.show_tool_execution(tool_calls)
    
    # Execute actual tools
    response = """TOOL_CALL: read_file
ARGS: {"path": "test.py"}

TOOL_CALL: edit_file
ARGS: {"path": "test.py", "action": "insert_before", "content": "# Enhanced system info script", "start_line": 1}"""
    
    results = execute_tool_calls(response)
    if results:
        rich_cli.show_tool_results(results)
    
    rich_cli.show_ai_response_start()
    rich_cli.stream_ai_response("Perfect! I've successfully read your test.py file and added a helpful comment at the top. The file now has better documentation.")
    rich_cli.show_ai_response_end()
    
    # Show status
    rich_cli.show_status("gemma3n:e2b", "demo-session-abc123")
    
    print("\n" + "="*60)
    rich_cli.console.print("[bold green]CLI TRANSFORMATION COMPLETE![/bold green]")
    rich_cli.console.print("[cyan]Your CLI now has:[/cyan]")
    rich_cli.console.print("  - Beautiful panels and tables")
    rich_cli.console.print("  - Syntax highlighting")
    rich_cli.console.print("  - Color-coded status messages")  
    rich_cli.console.print("  - Professional formatting")
    rich_cli.console.print("  - Windows-compatible output")
    rich_cli.console.print("\n[bold yellow]Ready for production use![/bold yellow]")

if __name__ == "__main__":
    demo_cli()