"""
AI-powered Intent Detection System for separating user intent analysis from tool execution.
Uses LLM to analyze user messages and determine what tools are needed.
Includes fallback mechanisms and keyword-based force tool usage.
"""

import json
import logging
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from llm.ollama_client import call_llm

logger = logging.getLogger(__name__)

@dataclass
class IntentAnalysis:
    needs_tools: bool
    reasoning: str
    user_message: str
    force_tools: bool = False
    suggested_retry: bool = False

class IntentDetector:
    """Uses AI to analyze user messages and determine tool requirements with enhanced fallback mechanisms."""
    
    def __init__(self):
        self.intent_prompt = """You are an intent analyzer. Analyze the user's message and determine if it requires using any coding tools.

CRITICAL: You MUST respond with ONLY a valid JSON object. No other text.

Format:
{"needs_tools": true/false, "reasoning": "Brief explanation"}

TOOL-REQUIRING PATTERNS:
- File operations: read, write, edit, create, modify, update, delete files
- Command execution: run, execute, install, build, test commands  
- File searching: find, search, locate files or patterns
- Directory operations: list, browse, navigate directories
- Code analysis: analyze, review, check code

Examples:
User: "hi there" -> {"needs_tools": false, "reasoning": "Simple greeting"}
User: "show me the config.py file" -> {"needs_tools": true, "reasoning": "User wants to read a file"}
User: "create a new test file" -> {"needs_tools": true, "reasoning": "User wants to create a file"}
User: "what's in the current directory?" -> {"needs_tools": true, "reasoning": "User wants to list directory contents"}
User: "run the tests" -> {"needs_tools": true, "reasoning": "User wants to execute a command"}

User message: """
        
        # Keywords that force tool usage
        self.force_tool_keywords = {
            '!read': 'read_file',
            '!write': 'write_file', 
            '!edit': 'edit_file',
            '!run': 'run_command',
            '!exec': 'run_command',
            '!find': 'find_files',
            '!search': 'find_files',
            '!list': 'list_directory',
            '!ls': 'list_directory'
        }
        
        # Patterns that suggest tool usage but might be missed by AI
        self.tool_hint_patterns = [
            r'\b(read|show|display|view|see|check|examine)\s+.*\.(py|js|json|txt|md|yml|yaml|toml|cfg|ini|log)',
            r'\b(create|write|make|generate|add)\s+.*\.(py|js|json|txt|md|yml|yaml|toml|cfg|ini)',
            r'\b(run|execute|start|launch)\s+.*\b(command|script|test|build|install)',
            r'\b(find|search|locate)\s+.*\b(file|pattern|function|class|variable)',
            r'\b(list|show|display)\s+.*\b(directory|folder|files)',
            r'\bwhat.*in.*\b(directory|folder)',
            r'\b(analyze|review|check|examine)\s+.*\b(code|file|project)'
        ]

    def analyze_intent(self, user_message: str) -> IntentAnalysis:
        """Use AI to analyze user message and determine tool requirements with enhanced fallbacks."""
        
        # Check for force tool keywords first
        force_tools = self._check_force_keywords(user_message)
        if force_tools:
            return IntentAnalysis(
                needs_tools=True,
                reasoning=f"Force tool keyword detected: {force_tools}",
                user_message=user_message,
                force_tools=True
            )
        
        # Use AI for intent analysis
        ai_analysis = self._get_ai_analysis(user_message)
        
        # If AI says no tools needed, check fallback patterns
        if not ai_analysis.needs_tools:
            fallback_check = self._check_fallback_patterns(user_message)
            if fallback_check:
                return IntentAnalysis(
                    needs_tools=True,
                    reasoning=f"Fallback pattern detected: {fallback_check}",
                    user_message=user_message,
                    suggested_retry=True
                )
        
        return ai_analysis
    
    def _check_force_keywords(self, message: str) -> Optional[str]:
        """Check for force tool keywords like !read, !exec, etc."""
        words = message.lower().split()
        for word in words:
            if word in self.force_tool_keywords:
                return word
        return None
    
    def _check_fallback_patterns(self, message: str) -> Optional[str]:
        """Check patterns that suggest tool usage but might be missed by AI."""
        message_lower = message.lower()
        
        for i, pattern in enumerate(self.tool_hint_patterns):
            if re.search(pattern, message_lower, re.IGNORECASE):
                pattern_names = [
                    "file operation pattern",
                    "file creation pattern", 
                    "command execution pattern",
                    "file search pattern",
                    "directory listing pattern",
                    "directory inquiry pattern",
                    "code analysis pattern"
                ]
                return pattern_names[min(i, len(pattern_names)-1)]
        
        return None
    
    def _get_ai_analysis(self, user_message: str) -> IntentAnalysis:
        """Get AI analysis for intent detection."""
        messages = [
            {"role": "system", "content": self.intent_prompt + user_message}
        ]
        
        try:
            # Get AI analysis
            response = call_llm(messages)
            
            # Clean and extract JSON from response
            response_clean = response.strip()
            
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{[^{}]*\}', response_clean)
            if json_match:
                json_str = json_match.group()
                analysis_data = json.loads(json_str)
            else:
                # Fallback: try to parse the whole response
                analysis_data = json.loads(response_clean)
            
            return IntentAnalysis(
                needs_tools=analysis_data.get("needs_tools", False),
                reasoning=analysis_data.get("reasoning", "AI analysis completed"),
                user_message=user_message
            )
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error analyzing intent: {e}")
            # Enhanced fallback - check patterns if AI fails
            fallback_check = self._check_fallback_patterns(user_message)
            if fallback_check:
                return IntentAnalysis(
                    needs_tools=True,
                    reasoning=f"AI failed, fallback pattern detected: {fallback_check}",
                    user_message=user_message,
                    suggested_retry=True
                )
            
            return IntentAnalysis(
                needs_tools=False,
                reasoning=f"AI analysis failed: {str(e)}",
                user_message=user_message
            )
    
    def suggest_retry_with_tools(self, user_message: str, ai_response: str) -> bool:
        """
        Suggest retry with tools if AI response seems like it should have used tools
        but didn't actually use any.
        """
        # Check if response mentions files/commands but no tools were used
        response_lower = ai_response.lower()
        
        retry_indicators = [
            "would need to",
            "you could",
            "you should", 
            "try running",
            "check the file",
            "look at the",
            "examine the",
            "file might be",
            "directory might",
            "command would be"
        ]
        
        for indicator in retry_indicators:
            if indicator in response_lower:
                return True
        
        # Also check if original message has tool patterns
        return self._check_fallback_patterns(user_message) is not None

# Global instance
intent_detector = IntentDetector()