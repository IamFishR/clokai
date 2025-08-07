import os
import re
import glob
import fnmatch
from pathlib import Path
from typing import List, Dict, Any
from config import PROJECT_ROOT
from tracking.tracker import tracker

def find_files(pattern: str = "*", search_type: str = "name", max_results: int = 100) -> str:
    """
    Find files using various search methods
    
    Args:
        pattern: Search pattern (filename, glob pattern, or regex)
        search_type: Type of search ("name", "glob", "regex", "content")
        max_results: Maximum number of results to return
    
    Returns:
        String with formatted search results
    """
    import time
    start_time = time.time()
    
    try:
        
        results = []
        project_path = Path(PROJECT_ROOT).resolve()
        
        if search_type == "name":
            # Search by filename (case-insensitive partial match)
            for root, dirs, files in os.walk(project_path):
                for file in files:
                    if pattern.lower() in file.lower():
                        rel_path = os.path.relpath(os.path.join(root, file), project_path)
                        results.append(rel_path)
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
                    
        elif search_type == "glob":
            # Search using glob patterns
            if not pattern.startswith("**/"):
                pattern = f"**/{pattern}"  # Make it recursive by default
            
            for file_path in glob.glob(os.path.join(project_path, pattern), recursive=True):
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path, project_path)
                    results.append(rel_path)
                    if len(results) >= max_results:
                        break
                        
        elif search_type == "regex":
            # Search using regex pattern
            try:
                regex = re.compile(pattern, re.IGNORECASE)
                for root, dirs, files in os.walk(project_path):
                    for file in files:
                        if regex.search(file):
                            rel_path = os.path.relpath(os.path.join(root, file), project_path)
                            results.append(rel_path)
                            if len(results) >= max_results:
                                break
                    if len(results) >= max_results:
                        break
            except re.error as e:
                return f"Invalid regex pattern: {e}"
                
        elif search_type == "content":
            # Search file contents (simple text search)
            for root, dirs, files in os.walk(project_path):
                # Skip common build/cache directories
                dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.venv']]
                
                for file in files:
                    # Only search text files
                    if file.endswith(('.py', '.js', '.ts', '.txt', '.md', '.json', '.yml', '.yaml', '.cfg', '.ini')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if pattern.lower() in content.lower():
                                    rel_path = os.path.relpath(file_path, project_path)
                                    results.append(rel_path)
                                    if len(results) >= max_results:
                                        break
                        except Exception:
                            continue  # Skip files we can't read
                if len(results) >= max_results:
                    break
        else:
            return f"Invalid search_type: {search_type}. Use: name, glob, regex, or content"
        
        # Format results
        if not results:
            return f"No files found matching pattern '{pattern}' using {search_type} search"
        
        result_text = f"Found {len(results)} file(s) matching '{pattern}' using {search_type} search:\n"
        for i, file_path in enumerate(results, 1):
            # Use forward slashes for consistency
            normalized_path = file_path.replace("\\", "/")
            result_text += f"{i}. {normalized_path}\n"
        
        if len(results) == max_results:
            result_text += f"\n(Limited to {max_results} results. Use max_results parameter to see more)"
        
        final_result = result_text.strip()
        
        # Track successful execution
        execution_time = int((time.time() - start_time) * 1000)
        try:
            tracker.track_tool_call("find_files", {"pattern": pattern, "search_type": search_type}, 
                                  final_result, execution_time)
        except:
            pass  # Don't break execution if tracking fails
        
        return final_result
        
    except Exception as e:
        error_msg = f"Error searching for files: {e}"
        execution_time = int((time.time() - start_time) * 1000)
        try:
            tracker.track_tool_call("find_files", {"pattern": pattern, "search_type": search_type}, 
                                  error_msg, execution_time, status='error', error_message=str(e))
        except:
            pass  # Don't break execution if tracking fails
        return error_msg

def list_directory(path: str = ".") -> str:
    """
    List contents of a directory with file/folder information
    
    Args:
        path: Directory path (relative to project root)
    
    Returns:
        String with formatted directory listing
    """
    import time
    start_time = time.time()
    
    try:
        
        project_path = Path(PROJECT_ROOT).resolve()
        target_path = (project_path / path).resolve()
        
        # Security check - ensure we're within project root
        if not str(target_path).startswith(str(project_path)):
            return "Error: Path is outside project directory"
        
        if not target_path.exists():
            return f"Directory '{path}' does not exist"
        
        if not target_path.is_dir():
            return f"'{path}' is not a directory"
        
        items = []
        for item in sorted(target_path.iterdir()):
            rel_path = item.relative_to(project_path)
            normalized_path = str(rel_path).replace("\\", "/")
            if item.is_dir():
                items.append(f"[DIR] {normalized_path}/")
            else:
                size = item.stat().st_size
                size_str = f"({size} bytes)" if size < 1024 else f"({size//1024}KB)"
                items.append(f"[FILE] {normalized_path} {size_str}")
        
        if not items:
            return f"Directory '{path}' is empty"
        
        result = f"Contents of '{path}':\n"
        result += "\n".join(items)
        
        # Track successful execution
        execution_time = int((time.time() - start_time) * 1000)
        try:
            tracker.track_tool_call("list_directory", {"path": path}, result, execution_time)
        except:
            pass  # Don't break execution if tracking fails
        
        return result
        
    except Exception as e:
        error_msg = f"Error listing directory '{path}': {e}"
        execution_time = int((time.time() - start_time) * 1000)
        try:
            tracker.track_tool_call("list_directory", {"path": path}, error_msg, execution_time, 
                                  status='error', error_message=str(e))
        except:
            pass  # Don't break execution if tracking fails
        return error_msg