from tools.file_ops import read_file, write_file, edit_file
from tools.command_runner import run_command
from tools.file_search import find_files, list_directory

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "run_command": run_command,
    "find_files": find_files,
    "list_directory": list_directory
}