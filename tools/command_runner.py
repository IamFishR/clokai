import subprocess

def run_command(cmd):
    """Execute shell command - tracking handled by smart_tool_system"""
    try:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=10)
        
        # Return structured data for tracking, but the tool output shows combined output
        # Store detailed info in a way that can be accessed by tracking
        output = result.stdout + result.stderr
        
        # Add execution details as attributes to the string (hacky but works)
        output_with_details = output
        setattr(output_with_details, '_cmd_details', {
            'command': cmd,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        })
        
        return output_with_details
        
    except subprocess.TimeoutExpired:
        error_msg = f"Command '{cmd}' timed out"
        setattr(error_msg, '_cmd_details', {
            'command': cmd,
            'returncode': -1,
            'stdout': '',
            'stderr': error_msg
        })
        return error_msg
        
    except Exception as e:
        error_msg = str(e)
        setattr(error_msg, '_cmd_details', {
            'command': cmd,
            'returncode': -1,
            'stdout': '',
            'stderr': error_msg
        })
        return error_msg