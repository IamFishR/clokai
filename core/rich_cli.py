"""
Professional CLI interface using Rich library for beautiful output
"""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich.rule import Rule
from rich.status import Status
from typing import List, Dict, Any

class RichCLI:
    """Beautiful CLI interface with rich formatting"""
    
    def __init__(self):
        self.console = Console()
        self.setup_styles()
    
    def setup_styles(self):
        """Setup custom styles for the CLI"""
        pass
    
    def show_welcome(self, session_id: str):
        """Display beautiful welcome message"""
        welcome_panel = Panel.fit(
            f"[bold green]Clokai - Claude Code Style AI Assistant[/bold green]\n\n"
            f"[dim]Session ID:[/dim] [yellow]{session_id}[/yellow]\n"
            f"[dim]Type '[/dim][bold cyan]/exit[/bold cyan][dim]' to quit, '[/dim][bold cyan]/help[/bold cyan][dim]' for commands[/dim]",
            border_style="green",
            title="[bold]Welcome[/bold]",
            subtitle="[dim]Powered by Ollama[/dim]"
        )
        self.console.print(welcome_panel)
        self.console.print()
    
    def show_user_input(self, prompt: str = "You"):
        """Show user input prompt"""
        return self.console.input(f"[bold blue]{prompt}[/bold blue]: ")
    
    def show_ai_response_start(self, name: str = "Clokai"):
        """Show AI response start"""
        self.console.print(f"[bold green]{name}[/bold green]: ", end="")
    
    def stream_ai_response(self, token: str):
        """Stream AI response token by token"""
        self.console.print(token, end="", markup=False)
    
    def show_ai_response_end(self):
        """End AI response"""
        self.console.print()  # New line
    
    def show_tool_execution(self, tool_calls: List[Dict[str, Any]]):
        """Show tool execution with progress"""
        if not tool_calls:
            return
        
        # Create a table for tool calls
        table = Table(
            title="[bold cyan]Executing Tools[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Arguments", style="white")
        table.add_column("Status", style="green")
        
        for call in tool_calls:
            args_preview = str(call.get('args', {}))[:50]
            if len(args_preview) >= 50:
                args_preview += "..."
            table.add_row(call.get('name', 'Unknown'), args_preview, "[yellow]Running...[/yellow]")
        
        self.console.print(table)
    
    def show_tool_results(self, results: str):
        """Show tool execution results with smart formatting"""
        if not results or results.strip() == "":
            return
        
        # Parse and format tool results
        lines = results.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                tool_name, result = line.split(':', 1)
                tool_name = tool_name.strip()
                result = result.strip()
                
                # Smart formatting based on tool type and content
                if tool_name == "read_file" and result and len(result) > 50:
                    # Show file content with syntax highlighting
                    filename = "file"  # We could extract this from args if needed
                    language = "python" if result.strip().startswith(('import ', 'def ', 'class ', 'from ')) else "text"
                    self.show_file_content(filename, result, language)
                elif tool_name == "run_command" and result:
                    # Show command output in a panel
                    command = "command"  # We could extract this from args if needed
                    self.show_command_output(command, result)
                else:
                    # Standard tool result display
                    # Determine status color
                    if any(word in result.lower() for word in ['error', 'failed', 'not found']):
                        status_color = "red"
                        status_icon = "[X]"
                    elif any(word in result.lower() for word in ['success', 'created', 'edited']):
                        status_color = "green" 
                        status_icon = "[OK]"
                    else:
                        status_color = "blue"
                        status_icon = "[i]"
                    
                    # Show tool result in a nice format
                    self.console.print(f"  {status_icon} [bold {status_color}]{tool_name}[/bold {status_color}]: {result}")
        
        self.console.print()  # Extra spacing
    
    def show_file_content(self, filename: str, content: str, language: str = "python"):
        """Show file content with syntax highlighting"""
        if not content.strip():
            self.console.print(f"[dim]File {filename} is empty[/dim]")
            return
        
        syntax = Syntax(
            content, 
            language, 
            theme="monokai", 
            line_numbers=True,
            word_wrap=True
        )
        
        panel = Panel(
            syntax,
            title=f"[bold cyan]{filename}[/bold cyan]",
            border_style="cyan"
        )
        
        self.console.print(panel)
    
    def show_command_output(self, command: str, output: str):
        """Show command execution output"""
        # Clean up output
        clean_output = output.strip() if output else "[dim]No output[/dim]"
        
        panel = Panel(
            clean_output,
            title=f"[bold yellow]Command: {command}[/bold yellow]",
            border_style="yellow"
        )
        
        self.console.print(panel)
    
    def show_error(self, message: str):
        """Show error message"""
        error_panel = Panel.fit(
            f"[bold red]ERROR:[/bold red] {message}",
            border_style="red"
        )
        self.console.print(error_panel)
    
    def show_help(self):
        """Show help message"""
        help_table = Table(
            title="[bold cyan]Available Commands[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )
        
        help_table.add_column("Command", style="cyan", no_wrap=True)
        help_table.add_column("Description", style="white")
        
        help_table.add_row("/help", "Show this help message")
        help_table.add_row("/exit", "Exit the CLI")
        help_table.add_row("/status", "Show current system status")
        help_table.add_row("/clear", "Clear conversation history")
        
        self.console.print(help_table)
        self.console.print()
        
        # Show force tool keywords
        keywords_table = Table(
            title="[bold yellow]Force Tool Keywords[/bold yellow]",
            show_header=True,
            header_style="bold magenta",
            border_style="yellow"
        )
        
        keywords_table.add_column("Keyword", style="yellow", no_wrap=True)
        keywords_table.add_column("Tool", style="white")
        keywords_table.add_column("Example", style="dim white")
        
        keywords_table.add_row("!read", "read_file", "!read config.py")
        keywords_table.add_row("!write", "write_file", "!write new_file.py")
        keywords_table.add_row("!edit", "edit_file", "!edit main.py")
        keywords_table.add_row("!run", "run_command", "!run python test.py")
        keywords_table.add_row("!exec", "run_command", "!exec ls -la")
        keywords_table.add_row("!find", "find_files", "!find *.py")
        keywords_table.add_row("!search", "find_files", "!search test")
        keywords_table.add_row("!list", "list_directory", "!list src/")
        keywords_table.add_row("!ls", "list_directory", "!ls .")
        
        self.console.print(keywords_table)
        self.console.print()
        
        # Show capabilities
        capabilities_panel = Panel(
            "[bold]Smart AI Assistant Capabilities:[/bold]\n"
            "- [cyan]Intelligent Tool Detection:[/cyan] Automatically detects when tools are needed\n"
            "- [cyan]File Operations:[/cyan] Read, write, edit files with precision\n"
            "- [cyan]Code Execution:[/cyan] Run shell commands and scripts\n"
            "- [cyan]Project Analysis:[/cyan] Search and analyze your codebase\n" 
            "- [cyan]Parallel Processing:[/cyan] Execute multiple tools simultaneously\n"
            "- [cyan]Error Recovery:[/cyan] Automatically retries failed operations\n"
            "- [cyan]Progress Tracking:[/cyan] Shows real-time execution status\n"
            "- [cyan]Force Keywords:[/cyan] Use ! keywords for immediate execution",
            title="[bold green]Smart Features[/bold green]",
            border_style="green"
        )
        self.console.print(capabilities_panel)
        
        # Show smart workflow
        workflow_panel = Panel(
            "[bold]Smart Workflow:[/bold]\n"
            "1. [yellow]You ask a question[/yellow] - Natural language, no special syntax\n"
            "2. [yellow]AI analyzes intent[/yellow] - Determines if tools are needed\n"
            "3. [yellow]Tools execute automatically[/yellow] - Parallel processing with progress\n"
            "4. [yellow]Error handling[/yellow] - Failed operations are automatically retried\n"
            "5. [yellow]Smart summary[/yellow] - AI provides final response with results",
            title="[bold blue]How It Works[/bold blue]",
            border_style="blue"
        )
        self.console.print(workflow_panel)
    
    def show_tool_report(self, validation_report: Dict, performance_report: Dict):
        """Show beautiful tool report"""
        # Validation report table
        validation_table = Table(
            title="[bold cyan]Tool Validation Report[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )
        
        validation_table.add_column("Metric", style="cyan")
        validation_table.add_column("Value", style="white")
        
        validation_table.add_row("Total Tool Calls", str(validation_report.get('total_tool_calls', 0)))
        validation_table.add_row("Blocked Calls", str(validation_report.get('blocked_calls', 0)))
        validation_table.add_row("Success Rate", f"{validation_report.get('success_rate', 0):.1f}%")
        
        self.console.print(validation_table)
        
        # Performance report table
        if performance_report:
            perf_table = Table(
                title="[bold cyan]Performance Report[/bold cyan]",
                show_header=True,
                header_style="bold magenta", 
                border_style="green"
            )
            
            perf_table.add_column("Tool", style="cyan")
            perf_table.add_column("Calls", style="white")
            perf_table.add_column("Avg Time", style="yellow")
            
            for tool_name, stats in performance_report.items():
                perf_table.add_row(
                    tool_name,
                    str(stats['call_count']),
                    f"{stats['avg_execution_time']:.3f}s"
                )
            
            self.console.print(perf_table)
    
    def show_status(self, model_name: str, session_id: str):
        """Show system status"""
        status_table = Table(
            title="[bold cyan]System Status[/bold cyan]",
            show_header=False,
            border_style="green"
        )
        
        status_table.add_column("Item", style="cyan", no_wrap=True)
        status_table.add_column("Value", style="white")
        
        status_table.add_row("Model", model_name)
        status_table.add_row("Session", session_id)
        status_table.add_row("Status", "[green]Active[/green]")
        status_table.add_row("Mode", "Offline (Local)")
        
        self.console.print(status_table)
    
    def clear_screen(self):
        """Clear the console screen"""
        self.console.clear()
    
    def show_separator(self):
        """Show a separator line"""
        self.console.print(Rule(style="dim"))

# Global rich CLI instance
rich_cli = RichCLI()