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

def write_file(path, content):
    """
    Writes content to a file, creating it if it doesn't exist or overwriting it if it does.

    Args:
        path: File path relative to PROJECT_ROOT.
        content: The content to write to the file.
    """
    start_time = time.time()
    
    try:
        full_path = Path(PROJECT_ROOT) / path
        
        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read original content if file exists
        original_content = ""
        if full_path.exists():
            with open(full_path, "r", encoding='utf-8') as f:
                original_content = f.read()
        
        # Write new content
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(content)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        if original_content:
            result = f"File {path} updated successfully."
        else:
            result = f"File {path} created successfully."
            
        # Track successful tool call
        tool_call_id = tracker.track_tool_call(
            "write_file", 
            {"path": path, "content": content[:100] + "..." if len(content) > 100 else content}, 
            result, 
            execution_time
        )
        
        # Track file snapshots
        if tool_call_id:
            tracker.track_file_snapshot(tool_call_id, str(full_path), "before", original_content)
            tracker.track_file_snapshot(tool_call_id, str(full_path), "after", content)
            
        return result
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        error_msg = f"Error writing file {path}: {str(e)}"
        
        # Track failed tool call
        tracker.track_tool_call(
            "write_file", 
            {"path": path, "content": content[:100] + "..." if len(content) > 100 else content}, 
            error_msg, 
            execution_time,
            status="error",
            error_message=str(e)
        )
        
        return error_msg

def edit_file(path, action, content, match_text=None, start_line=None, end_line=None):
    """
    Surgical file editing tool that supports various edit operations.
    
    Args:
        path: File path relative to PROJECT_ROOT
        action: One of 'insert_before', 'insert_after', 'replace_range', 'append_to_end'
        content: The content to insert/replace
        match_text: Text pattern to match for insert operations (optional)
        start_line: Starting line number for replace operations (1-based, optional)
        end_line: Ending line number for replace operations (1-based, optional)
    """
    start_time = time.time()
    
    try:
        full_path = Path(PROJECT_ROOT) / path
        
        if not full_path.exists():
            result = f"File {path} not found."
            execution_time = int((time.time() - start_time) * 1000)
            tracker.track_tool_call(
                "edit_file",
                {"path": path, "action": action, "content": content[:100] + "..." if len(content) > 100 else content},
                result,
                execution_time,
                status="error",
                error_message="File not found"
            )
            return result
        
        # Read original content
        with open(full_path, "r", encoding='utf-8') as f:
            original_content = f.read()
        
        lines = original_content.splitlines()
        new_lines = lines.copy()
        
        if action == "append_to_end":
            # Simply append to the end
            new_lines.append(content)
            
        elif action == "insert_before":
            if match_text:
                # Find line containing match_text
                target_line = None
                for i, line in enumerate(lines):
                    if match_text in line:
                        target_line = i
                        break
                if target_line is None:
                    raise ValueError(f"Match text '{match_text}' not found in file")
                new_lines.insert(target_line, content)
            elif start_line is not None:
                # Insert before specified line (convert to 0-based)
                target_line = start_line - 1
                if target_line < 0 or target_line > len(lines):
                    raise ValueError(f"Line number {start_line} is out of range")
                new_lines.insert(target_line, content)
            else:
                raise ValueError("Either match_text or start_line must be provided for insert_before")
                
        elif action == "insert_after":
            if match_text:
                # Find line containing match_text
                target_line = None
                for i, line in enumerate(lines):
                    if match_text in line:
                        target_line = i
                        break
                if target_line is None:
                    raise ValueError(f"Match text '{match_text}' not found in file")
                new_lines.insert(target_line + 1, content)
            elif start_line is not None:
                # Insert after specified line (convert to 0-based)
                target_line = start_line - 1
                if target_line < 0 or target_line >= len(lines):
                    raise ValueError(f"Line number {start_line} is out of range")
                new_lines.insert(target_line + 1, content)
            else:
                raise ValueError("Either match_text or start_line must be provided for insert_after")
                
        elif action == "replace_range":
            if start_line is None or end_line is None:
                # If no line numbers are provided, replace the entire file content
                new_lines = content.splitlines()
            else:
                # Convert to 0-based indexing
                start_idx = start_line - 1
                end_idx = end_line - 1
                
                if start_idx < 0 or end_idx >= len(lines) or start_idx > end_idx:
                    raise ValueError(f"Invalid line range: {start_line}-{end_line}")
                
                # Replace the range with new content (split by lines if multiline)
                content_lines = content.splitlines()
                new_lines[start_idx:end_idx + 1] = content_lines
            
        else:
            raise ValueError(f"Invalid action: {action}. Must be one of: insert_before, insert_after, replace_range, append_to_end")
        
        # Write the modified content
        new_content = "\n".join(new_lines)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(new_content)
        
        execution_time = int((time.time() - start_time) * 1000)
        result = f"File {path} edited successfully using {action} operation."
        
        # Track successful tool call
        tool_call_id = tracker.track_tool_call(
            "edit_file",
            {"path": path, "action": action, "content": content[:100] + "..." if len(content) > 100 else content},
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
        error_msg = f"Error editing file {path}: {str(e)}"
        
        # Track failed tool call
        tracker.track_tool_call(
            "edit_file",
            {"path": path, "action": action, "content": content[:100] + "..." if len(content) > 100 else content},
            error_msg,
            execution_time,
            status="error",
            error_message=str(e)
        )
        
        return error_msg
