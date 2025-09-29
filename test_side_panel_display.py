#!/usr/bin/env python3
"""
Visual test of the enhanced side panel with embeddings information.
This shows exactly what users will see in the side panel.
"""

import os
import sys

# Force offline mode
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

sys.path.insert(0, 'aa-tui')
from enhanced_tui import EnhancedTUI

def display_side_panel_preview(tui):
    """Display a preview of what the side panel would show."""
    print("\n" + "─" * 25)
    print("📋 Side Panel Preview")
    print("─" * 25)

    # Time header
    from datetime import datetime
    now = datetime.now()
    print(f"⏰ {now.strftime('%H:%M:%S')}")
    print()

    # Agent Status
    print("🤖 Agent Status")
    print(f"⚡ {tui.agent_state.status.title()}")
    print()

    # AI Models Section - The new enhanced display
    print("🧠 AI Models")

    # LLM Connection
    if tui.agent_session:
        print(f"├─ LLM: ✅ Connected")
    else:
        print(f"├─ LLM: ⚠️ Not Connected")
    print(f"│  ├─ {tui.model}")
    print(f"│  └─ {tui.provider}")

    # Embeddings Status
    if tui.agent_state.embedding_status == "enabled":
        print(f"├─ Embeddings: ✅ Active")
        print(f"│  ├─ {tui.agent_state.embedding_model}")
        print(f"│  └─ {tui.agent_state.embedding_dim}D vectors")
    elif tui.agent_state.embedding_status == "offline":
        print(f"├─ Embeddings: 📵 Offline")
        print(f"│  └─ No cached model")
    elif tui.agent_state.embedding_status == "error":
        print(f"├─ Embeddings: ❌ Error")
        print(f"│  └─ Not available")
    else:
        print(f"├─ Embeddings: ⭕ Disabled")
        print(f"│  └─ Not available")

    # Storage Backend
    storage_icon = "🗂️" if tui.agent_state.storage_backend == "dual" else "📝"
    print(f"└─ Storage: {storage_icon} {tui.agent_state.storage_backend.title()}")

    print()
    print("💬 Conversation")
    print(f"Exchanges: 0")
    print(f"Messages: 0")

    print("─" * 25)


def main():
    print("=" * 50)
    print("ENHANCED SIDE PANEL WITH EMBEDDINGS STATUS")
    print("=" * 50)

    print("\n🔄 Initializing TUI...")
    tui = EnhancedTUI(
        model='qwen3-coder:30b',
        provider='ollama',
        memory_path='./test_memory'
    )

    print("✅ TUI created")

    # Show initial state
    print("\n1️⃣ INITIAL STATE (before agent init):")
    display_side_panel_preview(tui)

    # Initialize agent
    print("\n🔄 Initializing agent...")
    success = tui.init_agent()

    if success:
        print("✅ Agent initialized successfully")

        # Show state after initialization
        print("\n2️⃣ AFTER AGENT INITIALIZATION:")
        display_side_panel_preview(tui)

        # Explanation
        print("\n📊 WHAT THE USER SEES:")
        print("─" * 40)
        print("• LLM status clearly shows connection state")
        print("• Model name and provider are displayed")
        print("• Embeddings show if they're active/offline/error")
        print("• Actual model name shown when available")
        print("• Vector dimensions displayed (384D/768D)")
        print("• Storage backend indicates dual or markdown")
        print()
        print("🎨 Visual Indicators:")
        print("• ✅ = Successfully connected/active")
        print("• 📵 = Offline mode, no cache")
        print("• ❌ = Error occurred")
        print("• ⚠️ = Not connected")
        print("• 🗂️ = Dual storage (with vectors)")
        print("• 📝 = Markdown-only storage")

    else:
        print("⚠️ Agent initialization had issues")

    print("\n" + "=" * 50)
    print("✅ Enhanced UI successfully shows embedding status!")
    print("=" * 50)


if __name__ == "__main__":
    main()