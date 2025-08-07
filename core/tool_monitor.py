import logging
import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class ToolCallMonitor:
    def __init__(self):
        self.blocked_calls_log = deque(maxlen=100)  # Keep last 100 blocked calls
        self.performance_stats = defaultdict(list)
        self.validation_stats = {
            'total_calls': 0,
            'blocked_calls': 0,
            'empty_args_blocks': 0,
            'consecutive_blocks': 0,
            'redundant_search_blocks': 0
        }
    
    def log_blocked_call(self, tool_name: str, args: Dict[str, Any], reason: str):
        """Log a blocked tool call with detailed information"""
        blocked_call = {
            'timestamp': datetime.now().isoformat(),
            'tool_name': tool_name,
            'args': args,
            'reason': reason,
            'block_type': self._classify_block_reason(reason)
        }
        
        self.blocked_calls_log.append(blocked_call)
        self.validation_stats['blocked_calls'] += 1
        
        # Update specific block type counters
        block_type = blocked_call['block_type']
        if block_type == 'empty_args':
            self.validation_stats['empty_args_blocks'] += 1
        elif block_type == 'consecutive':
            self.validation_stats['consecutive_blocks'] += 1
        elif block_type == 'redundant_search':
            self.validation_stats['redundant_search_blocks'] += 1
        
        logger.warning(f"TOOL_MONITOR: Blocked {tool_name} - {reason}")
    
    def log_successful_call(self, tool_name: str, args: Dict[str, Any], 
                           execution_time: float = None):
        """Log a successful tool call"""
        self.validation_stats['total_calls'] += 1
        
        if execution_time is not None:
            self.performance_stats[tool_name].append(execution_time)
            # Keep only last 50 execution times per tool
            if len(self.performance_stats[tool_name]) > 50:
                self.performance_stats[tool_name] = self.performance_stats[tool_name][-50:]
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Generate a validation statistics report"""
        total = self.validation_stats['total_calls']
        blocked = self.validation_stats['blocked_calls']
        
        report = {
            'total_tool_calls': total,
            'blocked_calls': blocked,
            'success_rate': ((total - blocked) / max(total, 1)) * 100,
            'block_breakdown': {
                'empty_args': self.validation_stats['empty_args_blocks'],
                'consecutive_limits': self.validation_stats['consecutive_blocks'],
                'redundant_searches': self.validation_stats['redundant_search_blocks']
            },
            'recent_blocked_calls': list(self.blocked_calls_log)[-10:] if self.blocked_calls_log else []
        }
        
        return report
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance statistics report"""
        report = {}
        
        for tool_name, times in self.performance_stats.items():
            if times:
                avg_time = sum(times) / len(times)
                report[tool_name] = {
                    'call_count': len(times),
                    'avg_execution_time': avg_time,
                    'min_execution_time': min(times),
                    'max_execution_time': max(times)
                }
        
        return report
    
    def _classify_block_reason(self, reason: str) -> str:
        """Classify the type of block based on reason text"""
        reason_lower = reason.lower()
        
        if 'empty' in reason_lower or 'invalid arguments' in reason_lower:
            return 'empty_args'
        elif 'consecutive' in reason_lower:
            return 'consecutive'
        elif 'redundant' in reason_lower:
            return 'redundant_search'
        else:
            return 'other'
    
    def reset_stats(self):
        """Reset all statistics (useful for new sessions)"""
        self.blocked_calls_log.clear()
        self.performance_stats.clear()
        self.validation_stats = {
            'total_calls': 0,
            'blocked_calls': 0,
            'empty_args_blocks': 0,
            'consecutive_blocks': 0,
            'redundant_search_blocks': 0
        }
    
    def export_logs(self, filepath: str):
        """Export blocked calls log to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'validation_stats': self.validation_stats,
                    'blocked_calls': list(self.blocked_calls_log),
                    'performance_stats': dict(self.performance_stats)
                }, f, indent=2)
            logger.info(f"Tool monitoring logs exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")

# Global monitor instance
tool_monitor = ToolCallMonitor()