import time
from pathlib import Path
from config import PROJECT_ROOT

def read_file(path):
    """Read file contents - tracking handled by smart_tool_system"""
    try:
        full_path = Path(PROJECT_ROOT) / path
        if not full_path.resolve().is_file():
            return f"File {path} not found."
        
        with open(full_path, "r", encoding='utf-8') as f:
            content = f.read()
        
        return content
        
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"

def write_file(path, content):
    """
    Writes content to a file, creating it if it doesn't exist or overwriting it if it does.
    Tracking handled by smart_tool_system.

    Args:
        path: File path relative to PROJECT_ROOT.
        content: The content to write to the file.
    """
    try:
        full_path = Path(PROJECT_ROOT) / path
        
        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file existed before
        file_existed = full_path.exists()
        
        # Write new content
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(content)
        
        if file_existed:
            return f"File {path} updated successfully."
        else:
            return f"File {path} created successfully."
            
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

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
    try:
        full_path = Path(PROJECT_ROOT) / path
        
        if not full_path.exists():
            return f"File {path} not found."
        
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
        
        return f"File {path} edited successfully using {action} operation."
        
    except Exception as e:
        return f"Error editing file {path}: {str(e)}"
