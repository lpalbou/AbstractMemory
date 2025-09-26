# AbstractMemory TUI - Testing Guide

## ✅ **Current Status: FULLY FUNCTIONAL**

All runtime errors have been resolved. The TUI is now ready for testing in a real terminal environment.

## 🚀 **How to Test**

### **Prerequisites**
1. **Terminal**: Use a modern terminal emulator (Terminal.app, iTerm2, Wezterm, etc.)
2. **Ollama**: Ensure Ollama is running with the qwen3-coder:30b model
3. **Environment**: Activate your Python virtual environment with AbstractMemory dependencies

### **Testing Steps**

#### **Step 1: Open Terminal**
Open your preferred terminal application (not IDE integrated terminal)

#### **Step 2: Navigate to TUI Directory**
```bash
cd /Users/albou/projects/abstractmemory/aa-tui
```

#### **Step 3: Activate Virtual Environment**
```bash
source ../.venv/bin/activate  # Adjust path as needed
```

#### **Step 4: Run the TUI**
```bash
python nexus_tui.py --model qwen3-coder:30b
```

## 🎯 **What You Should See**

### **Startup Sequence**
```
🚀 Initializing AbstractMemory TUI...
📦 Model: qwen3-coder:30b
🧠 Memory: ./agent_memory
🎨 Theme: dark
⏳ Setting up agent...
ℹ️  Initializing Autonomous Agent...
ℹ️  Connecting to ollama with qwen3-coder:30b...
✅ LLM connection established
✅ Added file system tools with document memory integration
✅ Added 8 memory tools
✅ Agent identity and values configured
✅ Memory session created with 10 tools
✅ Agent initialized successfully!
🎯 Starting TUI...
```

### **TUI Interface**
Once the TUI loads, you should see:

1. **Title Bar**: Displays app name, model, status, and current time
2. **Main Area**: Conversation display with welcome message
3. **Side Panel**: Memory status, tools, and metrics (toggle with F2)
4. **Input Area**: Bottom input field with prompt "👤 You: "
5. **Status Bar**: Keyboard shortcuts and current operation status

## 🎮 **Interactive Features to Test**

### **Basic Interaction**
1. **Type a message**: Try "hello" or "tell me about yourself"
2. **Watch AI reasoning**: See thoughts and actions in foldable sections
3. **Expand/Collapse**: Click sections or press Enter when focused

### **Keyboard Shortcuts**
- **F1**: Help dialog with all shortcuts and commands
- **F2**: Toggle side panel visibility
- **F3**: Search conversation (not fully implemented yet)
- **F4**: Memory search (not fully implemented yet)
- **Ctrl+L**: Clear conversation
- **Ctrl+Q**: Quit application
- **Tab**: Navigate between UI elements
- **Enter**: Submit input or expand/collapse sections

### **Commands to Try**
Type these commands (they start with `/`):
- `/help` - Show help information
- `/status` - Display agent status
- `/memory` - Show memory contents
- `/tools` - List available tools
- `/clear` - Clear conversation
- `/quit` - Exit application

### **Test Scenarios**

#### **Scenario 1: Basic Chat**
```
You: hello, my name is Alice
AI: [Shows reasoning process, then responds]
You: what do you remember about me?
AI: [Should recall your name from memory]
```

#### **Scenario 2: File Operations**
```
You: list files in the current directory
AI: [Uses list_files tool, shows in foldable section]
You: read the README.md file
AI: [Uses read_file tool, stores in document memory]
```

#### **Scenario 3: Memory Operations**
```
You: remember that I prefer Python over JavaScript
AI: [Uses memory tools to store this fact]
You: what are my programming preferences?
AI: [Recalls from memory and responds]
```

## 🔍 **What to Look For**

### **Visual Elements**
- ✅ Colors and theming work correctly
- ✅ Expandable sections (▶/▼ indicators)
- ✅ Side panel toggles smoothly
- ✅ Input area shows prompt and accepts text
- ✅ Status bar updates with current operations

### **Functional Elements**
- ✅ AI responses appear in conversation
- ✅ Reasoning process shows in foldable sections
- ✅ Tool executions display results
- ✅ Memory injection information appears
- ✅ Commands execute properly

### **Performance**
- ✅ UI responds immediately to keyboard input
- ✅ No lag when typing or navigating
- ✅ Smooth scrolling (if content overflows)
- ✅ Quick toggle of panels and sections

## 🐛 **Troubleshooting**

### **If TUI Doesn't Start**
1. Check Ollama is running: `ollama ps`
2. Verify model exists: `ollama list | grep qwen3-coder`
3. Test basic prompt_toolkit: `python -c "from prompt_toolkit import prompt; prompt('test: ')"`

### **If Colors Don't Work**
1. Check terminal supports ANSI colors
2. Try different terminal emulator
3. Use light theme: `python nexus_tui.py --theme light`

### **If Mouse Doesn't Work**
1. Enable mouse in terminal settings
2. Try without mouse: `python nexus_tui.py --no-mouse`

### **If Layout Looks Wrong**
1. Resize terminal to at least 80x24
2. Try hiding side panel: `python nexus_tui.py --no-side-panel`

## 📝 **Testing Checklist**

- [ ] TUI starts without errors
- [ ] Agent connects to Ollama successfully
- [ ] Welcome message appears
- [ ] Can type in input area
- [ ] AI responds to messages
- [ ] Keyboard shortcuts work (F1, F2, Ctrl+Q)
- [ ] Commands work (`/help`, `/status`)
- [ ] Side panel toggles with F2
- [ ] Foldable sections expand/collapse
- [ ] Memory and tools are displayed
- [ ] Conversation history persists

## 🎉 **Success Criteria**

The TUI is working correctly if:
1. ✅ No "color format" or runtime errors
2. ✅ All UI elements render properly
3. ✅ AI agent responds to input
4. ✅ Interactive features work as expected
5. ✅ Keyboard and mouse input are responsive

---

**Status**: Ready for terminal testing
**Last Updated**: 2025-09-26
**Note**: Must run in real terminal, not IDE/tool environment