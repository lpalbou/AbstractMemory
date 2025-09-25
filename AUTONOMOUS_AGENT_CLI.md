# 🤖 Autonomous Agent CLI REPL

**A standalone CLI interface for interacting with an autonomous ReAct agent powered by AbstractCore and AbstractMemory.**

## ✨ Features

- **🧠 Identity-Based Memory**: Persistent memory with subjective interpretation across sessions
- **🛠️ Tool Integration**: File system tools + memory manipulation tools
- **👁️ Real-Time Visibility**: See AI thoughts, reasoning, and actions in real-time
- **🔄 Session Persistence**: Agent remembers everything across restarts
- **🎨 Beautiful Interface**: Rich terminal formatting with status panels
- **⚙️ Configurable**: Customizable model, memory path, and identity

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure Ollama is running with qwen3-coder:30b
ollama pull qwen3-coder:30b
ollama serve

# Install dependencies
pip install rich  # For beautiful terminal output
```

### Launch the Agent

```bash
# Simple launch (uses defaults)
python autonomous_agent_cli.py

# Or use the launcher script
./run_agent.sh

# Custom configuration
python autonomous_agent_cli.py --model qwen3-coder:30b --memory-path ./my_agent --identity research_assistant
```

## 🧠 Agent Capabilities

### Memory System
- **Persistent Memory**: Remembers conversations, facts, and experiences across sessions
- **Identity-Based Interpretation**: Same facts interpreted differently based on agent's values
- **Subjective Experience**: Agent develops personality through accumulated experiences
- **Multi-Dimensional Storage**: Core memory, working memory, semantic facts, episodic events

### Available Tools

#### File System Tools (from AbstractCore)
- `list_files(path)`: List files and directories
- `read_file(path)`: Read file contents

#### Memory Tools (custom-built)
- `search_agent_memory(query)`: Search the agent's memory
- `remember_important_fact(fact)`: Store important facts
- `get_memory_context(topic)`: Get relevant context about a topic
- `interpret_fact_subjectively(fact)`: Apply agent's values to interpret facts
- `get_agent_identity()`: View agent's identity and values

## 💬 Example Interactions

### Basic Conversation
```
You: Hello! I'm working on a machine learning project.

🤔 Agent is thinking...

Agent: Hello! It's great to meet someone working on machine learning. I'd love to help with your project.

Let me remember this for future reference...
[Tool: remember_important_fact("User is working on a machine learning project")]
✅ Remembered: User is working on a machine learning project

What specific aspect of machine learning are you focusing on? I can help with:
- Algorithm implementation and optimization
- Data preprocessing and analysis
- Model evaluation and debugging
- Code review and best practices

Would you like me to take a look at any files in your project directory?
```

### File System Interaction
```
You: Can you see what files I have in my current directory?

🛠️ Agent is using tools...

[Tool: list_files(".")]
📁 Current directory contents:
- autonomous_agent_cli.py
- README.md
- abstractmemory/
- tests/
- requirements.txt

I can see you have a Python project with an AbstractMemory package and tests. Would you like me to examine any specific files to understand your project better?
```

### Memory Persistence
```
Session 1:
You: My ML project focuses on transformer architectures for NLP.
Agent: [Remembers this fact]

[Agent restart - new session]

Session 2:
You: What do you remember about my work?
Agent: I remember you're working on a machine learning project that focuses on transformer architectures for natural language processing. How is your transformer work progressing?
```

## ⚙️ Configuration Options

### Command Line Arguments

```bash
python autonomous_agent_cli.py [OPTIONS]

Options:
  --model MODEL            LLM model (default: qwen3-coder:30b)
  --provider PROVIDER      LLM provider (default: ollama)
  --memory-path PATH       Memory storage location (default: ./agent_memory)
  --identity NAME          Agent identity name (default: autonomous_assistant)
  --no-tools              Disable file system tools
  --no-memory-tools       Disable memory tools
  --no-rich               Disable rich terminal formatting
```

### Identity Configuration

The agent can be configured with different identities:

```bash
# Research assistant identity
python autonomous_agent_cli.py --identity research_assistant

# Code reviewer identity
python autonomous_agent_cli.py --identity code_reviewer

# Data analyst identity
python autonomous_agent_cli.py --identity data_analyst
```

Each identity has different core values that influence how it interprets information:

- **Research Assistant**: Analytical, discovery-focused, systematic investigation
- **Code Reviewer**: Quality-focused, security-conscious, best practices oriented
- **Data Analyst**: Pattern-recognition, insight-driven, evidence-based reasoning

## 🎮 Interactive Commands

### Built-in Commands
- `help` - Show help and available commands
- `status` - Display agent status and capabilities
- `clear` - Clear the terminal screen
- `quit` / `exit` / `q` - Exit the CLI (saves memory automatically)

### Example Workflows

#### Code Analysis Workflow
```
You: help me analyze the code structure
Agent: I'll help you analyze your code structure. Let me start by examining your directory...
[Uses list_files and read_file tools]
[Provides detailed analysis]
[Remembers findings for future reference]
```

#### Research Assistant Workflow
```
You: I need to research transformer attention mechanisms
Agent: I'll help you research transformer attention mechanisms systematically...
[Searches existing memory for related information]
[Provides comprehensive explanation]
[Remembers your research interests]
```

## 🔧 Technical Architecture

### Memory System
```
Agent Memory Structure:
├── Core Memory (Identity & Values)
├── Working Memory (Recent Context)
├── Semantic Memory (Validated Facts)
├── Episodic Memory (Historical Events)
└── Storage (Persistent Files)
    ├── verbatim/ (Objective Records)
    └── experiential/ (Subjective Interpretations)
```

### Tool Integration
```python
# File System Tools (AbstractCore)
@tool
def list_files(path: str) -> str:
    """List files and directories"""

@tool
def read_file(path: str) -> str:
    """Read file contents"""

# Memory Tools (Custom)
@tool
def search_agent_memory(query: str) -> str:
    """Search agent's memory"""

@tool
def remember_important_fact(fact: str) -> str:
    """Store important fact"""
```

## 🐛 Troubleshooting

### Common Issues

**"AbstractCore not available"**
```bash
# Install AbstractCore
pip install abstractcore
```

**"AbstractMemory not available"**
```bash
# Install from local directory
cd /path/to/abstractmemory
pip install -e .
```

**"Failed to connect to Ollama"**
```bash
# Ensure Ollama is running
ollama serve

# Pull required model
ollama pull qwen3-coder:30b
```

**Memory not persisting**
- Check that memory path is writable
- Verify agent exits gracefully (use `quit` command)

### Debug Mode

For verbose debugging:
```bash
# Enable debug logging
PYTHONPATH=/path/to/abstractmemory python autonomous_agent_cli.py --model qwen3-coder:30b
```

## 📊 Performance Notes

### Model Recommendations
- **qwen3-coder:30b**: Best overall performance, excellent reasoning
- **llama3.1:8b**: Faster responses, good for testing
- **granite3.3:8b**: Good alternative with reasoning capabilities

### Memory Scaling
- Memory grows incrementally with each interaction
- Automatic consolidation prevents excessive memory usage
- Large memory sets (1000+ interactions) may slow context retrieval

### Tool Performance
- File tools are fast for small-medium files
- Memory tools scale well up to 10k+ stored interactions
- Background memory operations don't block conversation

## 🔮 Advanced Usage

### Multiple Agent Identities
```bash
# Launch different specialized agents
python autonomous_agent_cli.py --identity researcher --memory-path ./researcher_memory
python autonomous_agent_cli.py --identity coder --memory-path ./coder_memory
python autonomous_agent_cli.py --identity analyst --memory-path ./analyst_memory
```

### Custom System Integration
```python
# Extend with custom tools
from autonomous_agent_cli import AutonomousAgentCLI
from abstractcore.tools import tool

@tool
def custom_analysis_tool(data: str) -> str:
    """Custom analysis functionality"""
    return analyze_data(data)

# Add to agent
cli = AutonomousAgentCLI(config)
cli.add_custom_tool(custom_analysis_tool)
```

## 🎯 Use Cases

### Software Development
- Code review and analysis
- Architecture planning
- Debug session assistance
- Documentation review

### Research & Analysis
- Literature review assistance
- Data analysis workflows
- Pattern recognition
- Insight generation

### Learning & Education
- Concept explanation
- Study session support
- Knowledge retention
- Progressive learning

---

## 🚀 Get Started Now

```bash
git clone [repository]
cd abstractmemory
python autonomous_agent_cli.py
```

**Start building with an AI that remembers, learns, and evolves with you!** 🧠✨