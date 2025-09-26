# AbstractMemory TUI

A state-of-the-art Terminal User Interface (TUI) for the AbstractMemory autonomous agent system, built with prompt_toolkit.

## Features

### 🎨 Modern UI/UX
- **Foldable Sections**: Click or press Enter/Space to expand/collapse thoughts, actions, and tool executions
- **Permanent Input Panel**: Always visible at bottom with autocomplete and command suggestions
- **Side Panel**: Toggle with F2 to show memory status, tools, and metrics
- **Modal Dialogs**: Help, search, and settings dialogs
- **Themes**: Dark and light themes with syntax highlighting
- **Mouse Support**: Click to interact, scroll, and select text

### 🧠 Memory Integration
- **Real-time Memory Display**: Working, semantic, episodic, and document memory
- **Memory Search**: Search through stored memories and documents
- **Context Metrics**: Live token usage and memory injection tracking
- **Persistent Sessions**: Conversations and memory persist across sessions

### 🔧 Agent Features
- **ReAct Reasoning**: Live display of agent's thought process
- **Tool Executions**: Expandable sections showing tool calls and results
- **Memory Injections**: See what memories were used in each response
- **Progress Indicators**: Visual feedback for long-running operations

### ⌨️ Keyboard Shortcuts
- **F1**: Show help dialog
- **F2**: Toggle side panel
- **F3**: Search conversation
- **F4**: Memory search
- **Ctrl+L**: Clear conversation
- **Ctrl+Q**: Quit application
- **Tab**: Cycle through UI elements
- **Enter**: Submit input / Toggle sections
- **Space**: Toggle foldable sections

## Installation

1. Ensure you have AbstractMemory and the nexus.py dependencies installed
2. Navigate to the aa-tui directory
3. Run the TUI:

```bash
python nexus_tui.py
```

## Usage Examples

### Basic Usage
```bash
# Use default settings
python nexus_tui.py

# Specify custom model
python nexus_tui.py --model qwen3-coder:30b

# Custom memory path
python nexus_tui.py --memory-path ./my_memory

# Light theme with no mouse support
python nexus_tui.py --theme light --no-mouse
```

### Advanced Configuration
```bash
# Custom layout and behavior
python nexus_tui.py --side-panel-width 40 --max-history 2000

# ReAct configuration
python nexus_tui.py --context-tokens 4000 --max-iterations 30

# Disable certain features
python nexus_tui.py --no-tools --no-memory-injection
```

## Commands

All commands start with `/`:

- `/help` - Show help information
- `/status` - Show agent status and capabilities
- `/memory` - Show memory contents
- `/memory N` - Set model max tokens to N
- `/tools` - Show available tools
- `/debug` - Show debugging information
- `/context` - Show last context used
- `/clear` - Clear conversation
- `/quit` - Exit application

## Architecture

### Directory Structure
```
aa-tui/
├── nexus_tui.py           # Main entry point
├── core/
│   ├── app.py             # Main Application class
│   ├── config.py          # Configuration management
│   └── session.py         # Session integration
├── ui/
│   ├── layouts/           # Layout components
│   ├── widgets/           # Custom widgets
│   ├── dialogs/           # Modal dialogs
│   └── styles/            # Themes and styling
├── handlers/              # Event handlers
└── utils/                 # Utility functions
```

### Key Components

#### FoldableSection Widget
- Expandable/collapsible content sections
- Mouse and keyboard interaction
- Visual indicators for state
- Nested folding support

#### MainLayout
- Manages overall UI structure
- Handles panel visibility
- Coordinates between components
- Progress indication

#### ConversationArea
- Displays conversation history
- Manages foldable entries
- Auto-scrolling and search
- System message support

#### SidePanel
- Memory status display
- Tools and metrics
- Agent status monitoring
- Collapsible sections

## Theming

The TUI supports customizable themes with:

- **Dark Theme** (default): Green/blue accent colors on black background
- **Light Theme**: Blue accent colors on white background
- **Syntax Highlighting**: Code blocks, JSON, and tool outputs
- **Semantic Colors**: Different colors for different memory types

## Integration

The TUI integrates seamlessly with the existing nexus.py infrastructure:

- Uses the same `AutonomousAgentCLI` class
- Maintains compatibility with all memory types
- Supports all existing tools and commands
- Preserves session state and history

## Performance

- **Efficient Rendering**: Only updates changed parts of the UI
- **Lazy Loading**: Content is generated on-demand
- **Memory Management**: Limits conversation history to prevent memory issues
- **Async Support**: Non-blocking operations for smooth interaction

## Troubleshooting

### Common Issues

1. **Agent not initializing**: Check model configuration and ensure Ollama is running
2. **No mouse support**: Try `--no-mouse` flag or check terminal compatibility
3. **Layout issues**: Try resizing terminal or adjusting panel width
4. **Memory errors**: Reduce `--max-history` or clear conversation with `/clear`

### Debug Mode

Enable debug information:
```bash
python nexus_tui.py --debug
```

Use the `/debug` command within the TUI for runtime information.

## Contributing

The TUI is designed to be extensible:

1. **Custom Widgets**: Add new widgets in `ui/widgets/`
2. **New Themes**: Define themes in `ui/styles/themes.py`
3. **Additional Dialogs**: Create dialogs in `ui/dialogs/`
4. **Enhanced Commands**: Extend `handlers/key_bindings.py`

## Future Enhancements

- **Plugin System**: Support for custom widgets and themes
- **Configuration UI**: Visual settings dialog
- **Export Features**: Save conversations in various formats
- **Advanced Search**: Regex and semantic search
- **Vim Key Bindings**: Alternative key binding modes
- **Split Panes**: Multiple conversation contexts

## License

Same as AbstractMemory project.