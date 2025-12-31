# Sidekick - Personal Co-Worker AI Assistant

Sidekick is an advanced multi-agent AI system built with LangGraph that orchestrates multiple specialized agents to complete complex tasks. It uses a sophisticated workflow with planning, parallel execution, and three-stage evaluation to ensure high-quality results.

## 🎯 Overview

Sidekick breaks down complex user requests into manageable subtasks, executes them in parallel when possible, and evaluates the results at multiple stages to ensure quality. It supports optional clarification questions, intelligent task planning, parallel worker execution, and comprehensive evaluation.

## 🏗️ Architecture

### Multi-Agent System

Sidekick uses a **single LangGraph** with multiple specialized nodes:

1. **Clarifier Agent** - Generates 3 optional clarifying questions to refine user requirements
2. **Planner Agent** - Breaks down tasks into subtasks and organizes them into parallel execution groups
3. **Plan Quality Evaluator** - Evaluates the plan structure before execution
4. **Worker Agents** - Execute subtasks in parallel groups using tools
5. **Collector** - Aggregates results from parallel workers (deferred execution)
6. **Per-Task Evaluator** - Evaluates individual subtask completion
7. **Overall Evaluator** - Comprehensively evaluates final task completion

### Workflow

```
START
  ↓
[Optional] Clarifier → Wait for User → Planner
  ↓
Planner → [Optional] Plan Quality Evaluator → Parallel Worker Group
  ↓
Collector → Per-Task Evaluator → [Next Group or] Overall Evaluator
  ↓
END (or back to Planner for refinement)
```

### Key Features

- **Optional Clarification**: Ask 3 clarifying questions to refine requirements (optional - can skip)
- **Intelligent Planning**: Breaks tasks into subtasks with dependency analysis
- **Parallel Execution**: Executes independent subtasks concurrently using `asyncio.gather`
- **Three-Stage Evaluation**:
  - **Plan Quality**: Evaluates plan structure before execution
  - **Per-Task**: Evaluates each subtask/group completion
  - **Overall**: Comprehensive final evaluation
- **Push Notifications**: Automatically creates a subtask for push notifications if requested
- **Single Output Coordination**: Ensures only one final output file is created (e.g., one PDF, not multiple)

## 📁 Project Structure

```
sidekick/
├── app.py                 # Gradio UI application
├── sidekick.py            # Main Sidekick class and graph orchestration
├── state.py               # State TypedDict definition
├── models.py              # Pydantic models for structured outputs
├── routing.py             # Routing functions for conditional edges
├── tools.py               # Tool definitions (browser, file management, search, PDF, push)
├── nodes/                 # Node implementations
│   ├── clarifier.py       # Clarifier and wait_for_user nodes
│   ├── planner.py         # Planner node
│   ├── workers.py         # Worker nodes (worker, process_subtask, parallel_worker_group)
│   ├── evaluators.py      # All evaluator nodes
│   └── collector.py       # Collector node (deferred execution)
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
└── sandbox/              # Output directory for generated files
```

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Setup

1. **Clone or navigate to the project directory**

2. **Create a virtual environment and install dependencies:**

   Using `uv` (recommended):
   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

   Or using `pip`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**

   Copy `env.example` to `.env` and fill in your API keys:
   ```bash
   cp env.example .env
   ```

   Required environment variables:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `SERPER_API_KEY` - Google Serper API key for web search
   - `PUSHOVER_USER` - Pushover user key (optional, for push notifications)
   - `PUSHOVER_TOKEN` - Pushover API token (optional, for push notifications)

4. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

## 💻 Usage

### Running the Application

```bash
uv run app.py
```

Or with `pip`:
```bash
python app.py
```

This will start a Gradio web interface in your browser.

### Using the UI

1. **Enter your task request** in the message box
2. **Optionally specify success criteria** in the success criteria box
3. **Optional: Get Clarifying Questions**
   - Click "Get Clarifying Questions (Optional)" to receive 3 questions
   - Answer them to refine your task (optional - you can skip this)
4. **Click "Go!"** to start task execution
   - The system will work through planning, execution, and evaluation
   - Results will appear in the chat interface

### Example Queries

- `"Create a 10-page PDF report on renewable energy trends"`
- `"Research the top 5 programming languages in 2024 and create a summary document. Send me a push notification when done."`
- `"Generate a comprehensive analysis of AI ethics and save it as a PDF"`

## 🔧 How It Works

### 1. Clarification (Optional)

The **Clarifier Agent** generates 3 questions to better understand your requirements. You can:
- Answer all 3 questions for refined execution
- Skip clarification and go directly to planning

Clarification answers are:
- Included in the planner's prompt
- Passed directly to workers in their system prompts
- Used to refine task requirements

### 2. Planning

The **Planner Agent**:
- Analyzes the task (with clarification answers if provided)
- Breaks it into subtasks with dependencies
- Groups subtasks into parallel execution groups
- Detects push notification requests and creates a final notification subtask
- Ensures single output coordination (one PDF, not multiple)

### 3. Plan Quality Evaluation (Optional)

The **Plan Quality Evaluator** checks:
- Task granularity (not too fine, not too coarse)
- Dependency correctness
- Parallel group efficiency
- Single output coordination

If the plan needs refinement, it loops back to the planner.

### 4. Parallel Execution

**Worker Agents** execute subtasks in parallel groups:
- Each group runs concurrently using `asyncio.gather`
- Workers have access to all tools (browser, search, file management, PDF generation, push notifications)
- Results are stored in state and passed between workers
- Workers receive clarification answers directly in their prompts

### 5. Per-Task Evaluation

After each parallel group completes:
- **Per-Task Evaluator** checks if each subtask met its success criteria
- If tasks need refinement, the system returns to the planner
- If all tasks passed, it moves to the next group or overall evaluation

### 6. Overall Evaluation

The **Overall Evaluator**:
- Comprehensively evaluates if all subtasks together meet the original goal
- Checks alignment with original user request
- Sends push notification if requested and task is successful
- Returns to planner if refinement is needed

## 🛠️ Available Tools

Workers have access to:

- **Web Browsing** (Playwright) - Navigate and retrieve web pages
- **Web Search** (Google Serper) - Search the internet
- **Wikipedia** - Query Wikipedia for information
- **File Management** - Read, write, and manage files in the `sandbox/` directory
- **PDF Generation** - Convert markdown content to PDF
- **Push Notifications** (Pushover) - Send push notifications to your device
- **Python Code Execution** - Run Python code with safety constraints

## 📊 State Management

The system uses a shared `State` TypedDict that includes:

- **Messages**: Conversation history
- **Clarification**: Questions, answers, and completion status
- **Planning**: Task plan, parallel groups, current group index
- **Execution**: Worker results, task completion status
- **Evaluation**: Scores, feedback, refinement needs

State is persisted using SQLite checkpoints, allowing for resumable execution.

## 🔄 Routing Logic

The system uses conditional edges to route based on state:

- **route_from_start**: Routes to clarifier (if questions needed) or planner
- **route_after_wait_for_user**: Routes based on clarification completion
- **route_after_planner**: Routes to plan quality evaluator or workers
- **route_after_plan_quality**: Routes back to planner (if refinement needed) or to workers
- **route_after_per_task_evaluation**: Routes to next group, overall evaluator, or back to planner
- **route_after_overall_evaluation**: Routes to END (if successful) or back to planner

## 🎨 UI Features

- **Chat Interface**: Interactive conversation with Sidekick
- **Optional Clarification**: Get and answer clarifying questions
- **Success Criteria Input**: Specify what success looks like
- **Real-time Updates**: See progress as tasks execute
- **Reset Functionality**: Start fresh conversations

## 🔐 Environment Variables

See `env.example` for all required variables:

- `OPENAI_API_KEY` - Required for LLM access
- `SERPER_API_KEY` - Required for web search
- `PUSHOVER_USER` - Optional, for push notifications
- `PUSHOVER_TOKEN` - Optional, for push notifications
- `LANGSMITH_*` - Optional, for tracing and monitoring

## 📝 Key Design Decisions

1. **Single Graph**: All agents in one LangGraph for unified state management
2. **Parallel Execution**: Uses `asyncio.gather` for true concurrency
3. **Deferred Execution**: Collector node waits for all parallel workers
4. **Three-Stage Evaluation**: Catches issues early and ensures quality
5. **Optional Clarification**: Users can skip clarification and go directly to execution
6. **Single Output Coordination**: Explicit instructions prevent multiple output files
7. **Push Notification as Task**: Planner creates a subtask for notifications (not hardcoded)

## 🐛 Troubleshooting

### Import Errors

If you see import errors, ensure:
- Virtual environment is activated
- All dependencies are installed: `uv pip install -r requirements.txt`
- Current directory is in Python path (handled automatically by `app.py`)

### Browser Issues

If Playwright browser fails:
```bash
playwright install chromium
```

### Push Notifications Not Working

- Ensure `PUSHOVER_USER` and `PUSHOVER_TOKEN` are set in `.env`
- Push notifications are only sent if:
  - User explicitly requests them in the query
  - Task completes successfully

### Multiple Output Files

If you're getting multiple PDFs instead of one:
- The planner should create only one final output subtask
- Workers should coordinate on a single shared output
- Check that intermediate files aren't being created

## 📚 Dependencies

Key dependencies:
- `langgraph` - Graph orchestration framework
- `langchain` - LLM integration and tools
- `gradio` - Web UI framework
- `playwright` - Browser automation
- `aiosqlite` - Async SQLite for checkpoints

See `requirements.txt` for the complete list.

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

---

**Note**: Sidekick uses OpenAI's GPT-4o-mini model by default. Ensure you have sufficient API credits for your usage.
