import subprocess
import time
from tracking.tracker import tracker

def run_command(cmd):
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=10)
        execution_time = int((time.time() - start_time) * 1000)
        
        output = result.stdout + result.stderr
        
        # Track successful tool call
        tool_call_id = tracker.track_tool_call(
            "run_command", 
            {"command": cmd}, 
            f"Exit code: {result.returncode}", 
            execution_time
        )
        
        # Track command execution details
        if tool_call_id:
            tracker.track_command_execution(
                tool_call_id, cmd, result.returncode, 
                result.stdout, result.stderr, execution_time
            )
        
        return output
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        
        # Track failed tool call
        tool_call_id = tracker.track_tool_call(
            "run_command", 
            {"command": cmd}, 
            error_msg, 
            execution_time,
            status="error",
            error_message=error_msg
        )
        
        # Track command execution details for timeout/errors
        if tool_call_id:
            tracker.track_command_execution(
                tool_call_id, cmd, -1, 
                "", error_msg, execution_time
            )
        
        return error_msg