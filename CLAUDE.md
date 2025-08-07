# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

Start the CLI REPL:
```bash
python cli.py
```

The application uses Ollama for local LLM inference. Ensure Ollama is running locally on port 11434 before starting the CLI.

## Project Architecture

This is a local Claude-style CLI tool that provides an offline AI coding assistant using Ollama. The architecture follows a modular design:

### Core Components

- **Session Management** (`core/session.py`): Handles the main REPL loop, manages conversation history, and coordinates between user input and LLM responses
- **LLM Integration** (`llm/ollama_client.py`): Manages communication with local Ollama API using the configured model (default: codellama)
- **Tool System** (`tools/`): Implements function calling capabilities for file operations and command execution

### Tool Registry System

The application uses a centralized tool registry pattern (`tools/tool_registry.py`) that maps tool names to functions:
- `read_file`: Read files from the project directory
- `write_file`: Apply surgical edits to files using line-based replacements
- `run_command`: Execute shell commands with timeout protection

### Configuration

- **Model Configuration** (`config.py`): Centralized settings for Ollama API URL, model selection, and project scope
- **System Prompts** (`prompts/system_prompt.txt`): Defines the AI assistant's behavior and capabilities

### Key Design Patterns

- **Offline-First**: All operations work without internet connectivity using local Ollama
- **Project-Scoped**: File operations are restricted to the current project directory for security
- **Structured Edits**: File modifications use line-based edit objects rather than full rewrites
- **Tool-Based Architecture**: Extensible function calling system for adding new capabilities

## Development Notes

- The chunker module (`core/chunker.py`) supports breaking large files into manageable chunks for processing
- All file paths are resolved relative to PROJECT_ROOT for security
- Command execution has built-in timeout protection (10 seconds default)
- The system uses simple conversation history management without persistence

## Tool Call Validation System

The application includes a comprehensive tool call validation and monitoring system (`core/tool_validator.py`, `core/tool_monitor.py`):

### Features
- **Empty Argument Blocking**: Prevents tool calls with empty or meaningless arguments
- **Consecutive Call Limiting**: Blocks excessive consecutive calls to the same tool
- **Redundant Search Prevention**: Caches file search results to avoid unnecessary duplicate searches
- **Performance Monitoring**: Tracks execution times and call statistics
- **Comprehensive Logging**: Logs all blocked calls with detailed reasons

### Configuration
Tool validation can be configured in `config.py`:
- `TOOL_CALL_VALIDATION`: Enable/disable validation (default: True)
- `MAX_CONSECUTIVE_SAME_TOOL`: Maximum consecutive calls to same tool (default: 2)
- `BLOCK_EMPTY_ARGS`: Block calls with empty arguments (default: True)
- `PREVENT_REDUNDANT_FILE_SEARCHES`: Cache and prevent duplicate file searches (default: True)
- `LOG_BLOCKED_TOOL_CALLS`: Log blocked calls for debugging (default: True)

### CLI Commands
- `/tool_report`: Display validation and performance statistics
- `/help`: Show available CLI commands