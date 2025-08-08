OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma-3n-e2b-it:latest"
CHUNK_SIZE = 100
PROJECT_ROOT = "."

# Database Configuration
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""  # Set your MySQL password here
DB_NAME = "clokai_tracking"

# Tool Call Validation Configuration
TOOL_CALL_VALIDATION = True
MAX_CONSECUTIVE_SAME_TOOL = 2
BLOCK_EMPTY_ARGS = True
PREVENT_REDUNDANT_FILE_SEARCHES = True
LOG_BLOCKED_TOOL_CALLS = True