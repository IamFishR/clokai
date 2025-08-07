import time
from pathlib import Path
from config import PROJECT_ROOT
from tracking.tracker import tracker

def read_file(path):
    start_time = time.time()
    
    try:
        full_path = Path(PROJECT_ROOT) / path
        if not full_path.resolve().is_file():
            result = f"File {path} not found."
            execution_time = int((time.time() - start_time) * 1000)
            
            # Track tool call
            tracker.track_tool_call(
                "read_file", 
                {"path": path}, 
                result, 
                execution_time,
                status="error",
                error_message="File not found"
            )
            return result
        
        with open(full_path, "r", encoding='utf-8') as f:
            content = f.read()
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Track successful tool call
        tracker.track_tool_call(
            "read_file", 
            {"path": path}, 
            f"Successfully read {len(content)} characters", 
            execution_time
        )
        
        return content
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        error_msg = f"Error reading file {path}: {str(e)}"
        
        # Track failed tool call
        tracker.track_tool_call(
            "read_file", 
            {"path": path}, 
            error_msg, 
            execution_time,
            status="error",
            error_message=str(e)
        )
        
        return error_msg

def write_file(path, edits):
    start_time = time.time()
    
    try:
        full_path = Path(PROJECT_ROOT) / path
        
        # Read original content for before snapshot
        original_content = ""
        if full_path.exists():
            with open(full_path, "r", encoding='utf-8') as f:
                original_content = f.read()
        
        # Handle both string content and structured edits
        if isinstance(edits, str):
            # Simple string content - append to file
            new_content = original_content + "\n" + edits if original_content else edits
        else:
            # Structured edits format
            lines = original_content.splitlines() if original_content else []
            for edit in edits:
                start = edit["start_line"]
                end = edit["end_line"]
                replacement = edit["replacement"]
                lines[start:end] = replacement
            new_content = "\n".join(lines)
        
        # Write new content
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(new_content)
        
        execution_time = int((time.time() - start_time) * 1000)
        result = f"File {path} updated successfully."
        
        # Track successful tool call
        tool_call_id = tracker.track_tool_call(
            "write_file", 
            {"path": path, "edits": edits}, 
            result, 
            execution_time
        )
        
        # Track file snapshots
        if tool_call_id:
            tracker.track_file_snapshot(tool_call_id, str(full_path), "before", original_content)
            tracker.track_file_snapshot(tool_call_id, str(full_path), "after", new_content)
        
        return result
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        error_msg = f"Error writing file {path}: {str(e)}"
        
        # Track failed tool call
        tracker.track_tool_call(
            "write_file", 
            {"path": path, "edits": edits}, 
            error_msg, 
            execution_time,
            status="error",
            error_message=str(e)
        )
        
        return error_msg