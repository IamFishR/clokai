import logging
from typing import Dict, Any, List, Optional
from config import (
    TOOL_CALL_VALIDATION, 
    MAX_CONSECUTIVE_SAME_TOOL, 
    BLOCK_EMPTY_ARGS,
    PREVENT_REDUNDANT_FILE_SEARCHES,
    LOG_BLOCKED_TOOL_CALLS
)
from core.tool_monitor import tool_monitor

logger = logging.getLogger(__name__)

class ToolCallValidator:
    def __init__(self):
        self.tool_call_history = []
        self.found_files_cache = {}
        self.session_context = {
            'consecutive_tool_counts': {},
            'recent_searches': [],
            'known_files': set()
        }
    
    def validate_tool_call(self, tool_name: str, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate if a tool call should be executed.
        Returns (should_execute: bool, reason: Optional[str])
        """
        if not TOOL_CALL_VALIDATION:
            return True, None
            
        # Check for empty/invalid arguments
        if BLOCK_EMPTY_ARGS and self._has_empty_args(tool_name, args):
            reason = f"Blocked {tool_name}: Empty or invalid arguments"
            self._log_blocked_call(tool_name, args, reason)
            return False, reason
        
        # Check for consecutive same tool calls
        if self._exceeds_consecutive_limit(tool_name):
            reason = f"Blocked {tool_name}: Exceeded consecutive call limit ({MAX_CONSECUTIVE_SAME_TOOL})"
            self._log_blocked_call(tool_name, args, reason)
            return False, reason
            
        # Check for redundant file searches
        if PREVENT_REDUNDANT_FILE_SEARCHES and self._is_redundant_file_search(tool_name, args):
            reason = f"Blocked {tool_name}: Redundant file search"
            self._log_blocked_call(tool_name, args, reason)
            return False, reason
        
        return True, None
    
    def record_tool_call(self, tool_name: str, args: Dict[str, Any], result: str, execution_time: float = None):
        """Record a successful tool call for context tracking"""
        self.tool_call_history.append({
            'tool': tool_name,
            'args': args,
            'result': result
        })
        
        # Log successful call in monitor
        tool_monitor.log_successful_call(tool_name, args, execution_time)
        
        # Update consecutive tool counts
        if tool_name in self.session_context['consecutive_tool_counts']:
            self.session_context['consecutive_tool_counts'][tool_name] += 1
        else:
            # Reset all counts when a new tool is used
            self.session_context['consecutive_tool_counts'] = {tool_name: 1}
        
        # Cache file search results
        if tool_name == "find_files" and "Found" in result:
            pattern = args.get('pattern', args.get('arg1', ''))
            if pattern:
                self.found_files_cache[pattern] = result
                self._extract_found_files(result)
    
    def reset_context(self):
        """Reset context for new conversation or user input"""
        self.session_context['consecutive_tool_counts'] = {}
        self.session_context['recent_searches'].clear()
    
    def _has_empty_args(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Check if tool has empty or meaningless arguments"""
        if not args:
            return True
            
        # Tool-specific validation
        if tool_name == "find_files":
            pattern = args.get('pattern', args.get('arg1', ''))
            # Empty pattern or wildcard-only pattern without specific intent
            if not pattern or pattern == '*':
                return True
        
        elif tool_name == "read_file":
            path = args.get('path', args.get('arg1', ''))
            if not path or path.strip() == '':
                return True
                
        elif tool_name == "run_command":
            cmd = args.get('cmd', args.get('arg1', ''))
            if not cmd or cmd.strip() == '':
                return True
        
        return False
    
    def _exceeds_consecutive_limit(self, tool_name: str) -> bool:
        """Check if tool has been called too many times consecutively"""
        count = self.session_context['consecutive_tool_counts'].get(tool_name, 0)
        return count >= MAX_CONSECUTIVE_SAME_TOOL
    
    def _is_redundant_file_search(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Check if this file search is redundant"""
        if tool_name != "find_files":
            return False
            
        pattern = args.get('pattern', args.get('arg1', ''))
        search_type = args.get('search_type', args.get('arg2', 'name'))
        
        # Check if we've already searched for this pattern
        if pattern in self.found_files_cache:
            return True
            
        # Check if we've done a similar search recently
        recent_search = f"{pattern}:{search_type}"
        if recent_search in self.session_context['recent_searches']:
            return True
            
        # Add to recent searches
        self.session_context['recent_searches'].append(recent_search)
        # Keep only last 5 searches
        if len(self.session_context['recent_searches']) > 5:
            self.session_context['recent_searches'].pop(0)
            
        return False
    
    def _extract_found_files(self, result: str):
        """Extract found filenames from search results and cache them"""
        lines = result.split('\n')
        for line in lines:
            if line.strip() and not line.startswith('Found') and not line.startswith('No files'):
                # Extract filename from numbered results like "1. CLAUDE.md"
                parts = line.strip().split('. ', 1)
                if len(parts) > 1:
                    filename = parts[1].strip()
                    self.session_context['known_files'].add(filename)
    
    def _log_blocked_call(self, tool_name: str, args: Dict[str, Any], reason: str):
        """Log blocked tool calls for debugging"""
        if LOG_BLOCKED_TOOL_CALLS:
            logger.warning(f"BLOCKED TOOL CALL: {reason} - Tool: {tool_name}, Args: {args}")
        
        # Log in monitor for comprehensive tracking
        tool_monitor.log_blocked_call(tool_name, args, reason)
    
    def get_known_files(self) -> set:
        """Get set of files that have been discovered in this session"""
        return self.session_context['known_files'].copy()
    
    def suggest_alternative(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        """Suggest alternative actions when a tool call is blocked"""
        if tool_name == "find_files":
            pattern = args.get('pattern', '')
            if pattern in self.found_files_cache:
                return f"File search for '{pattern}' was already performed. Previous result: {self.found_files_cache[pattern]}"
            
            known_files = self.get_known_files()
            if known_files:
                matching_files = [f for f in known_files if pattern.lower() in f.lower()]
                if matching_files:
                    return f"Files matching '{pattern}' already found: {', '.join(matching_files)}"
        
        return None

# Global validator instance
tool_validator = ToolCallValidator()