# System Flow Diagram

## Current Architecture: Separated Intent Detection → Tool Execution

```
┌─────────────────┐
│   User Input    │
│    "hi" or      │  🗄️ DB: Start session tracking
│ "show me reqs"  │  📝 LOG: User input logged
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  STEP 1: AI     │  📝 LOG: Intent analysis request
│ Intent Analysis │  🗄️ DB: Track interaction start
│ "Does this need │
│    tools?"      │
└─────────────────┘
         │
    ┌────▼────┐
    │ Yes/No? │  📝 LOG: Intent result logged
    └────┬────┘
         │
    ┌────▼────────────────────────────────┐
    │              Decision                │
    └────┬─────────────────────────┬──────┘
         │ No                      │ Yes
         ▼                         ▼
┌─────────────────┐    ┌─────────────────────────┐
│  Normal AI      │    │    STEP 2: Send All     │
│   Response      │    │   Available Tools to AI │  📝 LOG: Tools list sent to AI
│                 │    │                         │
│ "Hi! How can    │    │ - read_file            │
│ I help you?"    │    │ - write_file           │
└─────────────────┘    │ - edit_file            │
         │              │ - run_command          │
         │              │ - find_files           │
         │              │ - list_directory       │
         │              └─────────────────────────┘
         │                          │
         │                          ▼
         │              ┌─────────────────────────┐
         │              │   AI Decides & Uses     │
         │              │   Tools as Needed       │  📝 LOG: AI response with tools
         │              │                         │
         │              │ "I'll read the          │
         │              │ requirements file..."   │
         │              └─────────────────────────┘
         │                          │
         │                          ▼
         │              ┌─────────────────────────┐
         │              │   Tool Execution        │  🗄️ DB: Each tool call tracked
         │              │   (Project handles)     │  📝 LOG: Tool execution details
         │              │                         │  ⏱️ DB: Execution time recorded
         │              │ read_file("reqs.txt")   │  ✅ DB: Success/error status
         │              └─────────────────────────┘
         │                          │
         │                          ▼
         │              ┌─────────────────────────┐
         │              │   Summary + Results     │  📝 LOG: Tool results logged
         │              │                         │  🗄️ DB: Final response saved
         │              │ ✓ read_file completed   │
         │              │ + File contents shown   │
         │              └─────────────────────────┘
         │                          │
         └──────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│        FINAL: Complete Interaction              │  🗄️ DB: Complete interaction
│                                                 │  📊 DB: Update session stats
│   Final AI response sent to user               │  📝 LOG: Session completion
└─────────────────────────────────────────────────┘
```

## Example 1: "hi"

```
User: "hi"
  ↓
Step 1: AI Intent → "Simple greeting" (needs_tools: false)
  ↓
Normal Response: "Hi! How can I help you?"
```

## Example 2: "what are the installed requirements for this project?"

```
User: "what are the installed requirements for this project?"
  ↓
Step 1: AI Intent → "User wants to check project requirements" (needs_tools: true)
  ↓
Step 2: System sends ALL available tools to AI:
  - read_file: Read file contents
  - write_file: Create new files  
  - edit_file: Edit existing files
  - run_command: Execute shell commands
  - find_files: Search for files
  - list_directory: List directory contents
  ↓
AI Response: "I'll check the requirements file for you"
AI Uses: read_file(file_path="requirements.txt")
  ↓
Tool Execution: Project reads requirements.txt
  ↓
Results: File contents displayed
  ↓
Summary: "✓ read_file completed"
  ↓
Final AI Response: "Here are the installed requirements: [shows file content]"
```

## Database & Logging Points:

### 🗄️ **Database Tracking** (via `tracker.py`):
- **Session Start**: New session with unique ID
- **Interaction Start**: Each user message tracked with timestamp
- **Tool Calls**: Each tool execution with args, results, timing, success/error
- **Interaction Complete**: Final response, model used, total time
- **Session Stats**: Updated counts and metrics

### 📝 **Logging Points** (via Python `logging`):
- **User Input**: Every message received
- **Intent Analysis**: AI reasoning and decision
- **Tool Requests**: Which tools sent to AI
- **Tool Execution**: Detailed execution logs with errors
- **Results**: Tool outputs and summaries
- **Session Events**: Start/stop/error events

### 📊 **What Gets Stored**:
- User messages & timestamps
- Intent analysis results  
- Tool call arguments & responses
- Execution times & success rates
- Session duration & interaction counts
- Error messages & debugging info

## Key Benefits:

1. **Clean Separation**: Intent detection is separate from tool execution
2. **AI-Powered**: Uses AI intelligence instead of complex regex patterns  
3. **Simple Flow**: Just 2 steps - "Need tools?" → "Here are tools"
4. **Smart AI**: AI decides which tools to use from the available list
5. **Automatic Summary**: Shows what was accomplished
6. **Full Tracking**: Everything logged and stored for analysis

## Visual Flow:

```
┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│     User     │───▶│  AI Intent  │───▶│ Tools (if    │
│   Message    │    │  Analysis   │    │   needed)    │
└──────────────┘    └─────────────┘    └──────────────┘
                                              │
                                              ▼
┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   Summary    │◀───│    Tool     │◀───│  AI Response │
│ & Results    │    │  Execution  │    │  with Tools  │
└──────────────┘    └─────────────┘    └──────────────┘
```

This architecture makes the system much cleaner and more predictable!