"""
Tool Request/Response Protocol for handling communication between AI and tool system.
"""

import json
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from tools.tool_registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

@dataclass
class ToolRequest:
    tool_name: str
    description: str
    available_args: Dict[str, str]

@dataclass
class ToolResponse:
    success: bool
    result: Any
    error: str = None
    execution_time: float = 0.0

class ToolProtocol:
    """Handles tool availability requests and execution coordination."""
    
    def get_available_tools(self, requested_tools: List[str]) -> List[ToolRequest]:
        """Return tool descriptions for requested tools."""
        available_tools = []
        
        tool_descriptions = {
            "read_file": {
                "description": "Read contents of a file",
                "args": {"file_path": "Path to the file to read"}
            },
            "write_file": {
                "description": "Create a new file with content", 
                "args": {"file_path": "Path for new file", "content": "Content to write"}
            },
            "edit_file": {
                "description": "Edit existing file with surgical modifications",
                "args": {"file_path": "Path to file", "edit_type": "insert_before/after/replace_range/append", "content": "New content", "line_number": "Target line (optional)"}
            },
            "run_command": {
                "description": "Execute shell command",
                "args": {"command": "Command to execute", "timeout": "Timeout in seconds (optional)"}
            },
            "find_files": {
                "description": "Search for files by name/pattern",
                "args": {"pattern": "Search pattern", "directory": "Directory to search (optional)"}
            },
            "list_directory": {
                "description": "List contents of directory", 
                "args": {"directory": "Directory path (optional, defaults to current)"}
            }
        }
        
        for tool_name in requested_tools:
            if tool_name in tool_descriptions and tool_name in TOOL_REGISTRY:
                tool_info = tool_descriptions[tool_name]
                available_tools.append(ToolRequest(
                    tool_name=tool_name,
                    description=tool_info["description"],
                    available_args=tool_info["args"]
                ))
            else:
                logger.warning(f"Requested tool '{tool_name}' not available")
        
        return available_tools
    
    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResponse:
        """Execute a single tool with given arguments."""
        import time
        
        if tool_name not in TOOL_REGISTRY:
            return ToolResponse(
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found in registry"
            )
        
        try:
            start_time = time.time()
            tool_function = TOOL_REGISTRY[tool_name]
            result = tool_function(**args)
            execution_time = time.time() - start_time
            
            return ToolResponse(
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ToolResponse(
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )
    
    def generate_summary(self, tool_responses: List[tuple]) -> str:
        """Generate summary of tool operations completed."""
        if not tool_responses:
            return "No tools were executed."
        
        successful_operations = []
        failed_operations = []
        
        for tool_name, response in tool_responses:
            if response.success:
                successful_operations.append(f"✓ {tool_name}")
            else:
                failed_operations.append(f"✗ {tool_name}: {response.error}")
        
        summary_parts = []
        
        if successful_operations:
            summary_parts.append(f"Completed: {', '.join(successful_operations)}")
        
        if failed_operations:
            summary_parts.append(f"Failed: {', '.join(failed_operations)}")
        
        return " | ".join(summary_parts)

# Global instance
tool_protocol = ToolProtocol()