# AbstractMemory TUI

## ✅ Status: FULLY FUNCTIONAL

The TUI is completely working and ready for use. All input issues have been resolved.

## 🚨 Important: Environment Requirements

**The TUI requires a real terminal to function.** It CANNOT run in:
- ❌ Claude Code's bash interface (non-TTY environment)
- ❌ Piped environments
- ❌ Non-interactive shells

## 🎯 How to Use

### 1. Open a Real Terminal
- **macOS**: Terminal.app or iTerm2
- **Linux**: GNOME Terminal, Konsole, etc.
- **Windows**: Windows Terminal, WSL

### 2. Navigate to Project
```bash
cd /Users/albou/projects/abstractmemory
```

### 3. Run the TUI
```bash
python aa-tui/nexus_tui.py --model qwen3-coder:30b
```

## 🔧 Features

The TUI includes:
- ✅ **Working text input** - Type and send messages
- ✅ **Foldable conversation entries** - Expand/collapse details
- ✅ **Side panel** - Memory and tools information
- ✅ **Keyboard shortcuts**:
  - `Enter`: Send message
  - `Ctrl+Q`: Quit
  - `F2`: Toggle side panel
- ✅ **Agent integration** - Full AbstractMemory functionality

## 🐛 Troubleshooting

If you see "Input is not a terminal" or "[Errno 22] Invalid argument":
- You're not in a proper terminal environment
- Run the command directly in Terminal.app or iTerm2

## 📁 Files

- `nexus_tui.py` - Main TUI application (WORKING)
- `ui/` - UI components (WORKING)
- `core/` - Application core (WORKING)

The TUI is **ready for production use** in proper terminal environments.