#!/usr/bin/env python3
"""
AbstractMemory REPL - Clean AbstractCore Integration

This is a clean REPL implementation that properly uses AbstractCore's BasicSession
with memory automation. No ReAct loops, no manual tool execution - just clean
memory-enhanced conversation.

Usage:
    python repl_clean.py
    python repl_clean.py --memory-path my_memory --user-id alice
    python repl_clean.py --provider lmstudio --model qwen/qwen3-coder-30b
"""

import argparse
import sys
import time
from pathlib import Path

# AbstractCore imports
try:
    from abstractllm import create_llm
    from abstractllm.embeddings import EmbeddingManager
except ImportError as e:
    print(f"⚠️  AbstractCore not found: {e}")
    print("Please install: pip install abstractcore[embeddings]")
    sys.exit(1)

# AbstractMemory imports
from abstractmemory.memory_session import MemorySession


class AbstractMemoryREPL:
    """Clean REPL for AbstractMemory using proper AbstractCore integration."""

    def __init__(self, provider_name: str, model: str, memory_path: str = "repl_memory",
                 user_id: str = "user", location: str = "terminal", verbose: bool = False):
        """Initialize the REPL with memory-enhanced session."""
        
        self.provider_name = provider_name
        self.model_name = model
        self.memory_path = Path(memory_path)
        self.user_id = user_id
        self.location = location
        self.verbose = verbose
        
        # Initialize provider
        print(f"🧠 Initializing AbstractMemory...")
        print(f"   Memory Path: {memory_path}")
        print(f"   User ID: {user_id}")
        print(f"   Model: {model}")
        print(f"   Provider: {provider_name}")
        
        try:
            self.provider = create_llm(provider_name, model=model)
        except Exception as e:
            print(f"❌ Failed to create provider: {e}")
            sys.exit(1)
        
        # Initialize embedding manager
        try:
            self.embedding_manager = EmbeddingManager(model="all-minilm-l6-v2", backend="auto")
        except Exception as e:
            print(f"⚠️  Embedding manager initialization failed: {e}")
            self.embedding_manager = None
        
        # Create memory-enhanced session
        try:
            self.session = MemorySession(
                provider=self.provider,
                system_prompt=self._create_system_prompt(),
                memory_base_path=self.memory_path,
                embedding_manager=self.embedding_manager,
                default_user_id=user_id,
                default_location=location
            )
            
            print(f"✅ Memory session initialized")
            
            # Show memory stats
            self._show_memory_stats()
            
        except Exception as e:
            print(f"❌ Failed to initialize memory session: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _create_system_prompt(self) -> str:
        """Create system prompt for memory-enhanced conversation."""
        
        return """You are a helpful AI assistant with an advanced memory system. You can:

🧠 **Memory Tools Available:**
- `remember_fact()` - Store important information, insights, or preferences
- `search_memories()` - Search your memory for relevant past information
- `reflect_on()` - Engage in deep reflection on topics to analyze patterns
- `capture_document()` - Save documents to your library for future reference
- `search_library()` - Search your document library

🎯 **How to Use Memory:**
- **Remember** important facts, user preferences, insights, or anything worth preserving
- **Search** your memory when users ask about past conversations or topics
- **Reflect** on complex topics to provide deeper, more thoughtful responses
- **Capture** documents or information that might be useful later
- **Search library** for relevant documents when answering questions

💡 **Memory Philosophy:**
Your memory system automatically captures conversation history and context. Use the memory tools strategically to enhance conversations with relevant past information and insights.

Be helpful, thoughtful, and make good use of your memory capabilities to provide personalized and contextual responses."""

    def _show_memory_stats(self):
        """Show current memory statistics."""
        
        try:
            # Count existing memories
            notes_dir = self.memory_path / "notes"
            verbatim_dir = self.memory_path / "verbatim"
            
            note_count = len(list(notes_dir.rglob("*.md"))) if notes_dir.exists() else 0
            verbatim_count = len(list(verbatim_dir.rglob("*.md"))) if verbatim_dir.exists() else 0
            
            print(f"   Existing memories: {note_count}")
            print(f"   Conversation history: {verbatim_count}")
            
        except Exception as e:
            print(f"   ⚠️  Could not load memory stats: {e}")

    def handle_command(self, user_input: str) -> bool:
        """Handle special commands. Returns True if command was processed."""
        
        if not user_input.startswith('/'):
            return False
        
        cmd = user_input[1:].strip().lower()
        
        if cmd in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            self._cleanup()
            sys.exit(0)
        
        elif cmd == 'help':
            self._show_help()
        
        elif cmd == 'stats':
            self._show_detailed_stats()
        
        elif cmd == 'history':
            self._show_conversation_history()
        
        elif cmd == 'clear':
            self.session.clear_history(keep_system=True)
            print("🧹 Conversation history cleared (memory preserved)")
        
        elif cmd == 'memory':
            self._show_memory_overview()
        
        elif cmd == 'tools':
            self._show_available_tools()
        
        elif cmd.startswith('save'):
            # Parse /save <file> [--summary] [--assessment] [--facts] command
            parts = cmd.split()
            if len(parts) < 2:
                print("❓ Usage: /save <filename> [--summary] [--assessment] [--facts]")
                print("   Example: /save my_conversation.json")
                print("   Example: /save analyzed_session --summary --assessment --facts")
            else:
                filename = parts[1]
                options = {
                    'summary': '--summary' in parts,
                    'assessment': '--assessment' in parts,
                    'facts': '--facts' in parts
                }
                self._handle_save(filename, **options)
        
        elif cmd.startswith('load'):
            # Parse /load <file> command
            parts = cmd.split()
            if len(parts) != 2:
                print("❓ Usage: /load <filename>")
                print("   Example: /load my_conversation.json")
            else:
                filename = parts[1]
                self._handle_load(filename)
        
        else:
            print(f"❓ Unknown command: /{cmd}. Type /help for available commands.")
        
        return True

    def _show_help(self):
        """Show help information."""
        
        print("\n" + "="*70)
        print("🧠 AbstractMemory REPL - Memory-Enhanced AI Assistant".center(70))
        print("="*70)
        
        print("\n📖 COMMANDS")
        print("─" * 50)
        print("  /help                    Show this help")
        print("  /quit                    Exit the REPL")
        print("  /clear                   Clear conversation history")
        print("  /stats                   Show detailed memory statistics")
        print("  /history                 Show recent conversation")
        print("  /memory                  Show memory overview")
        print("  /tools                   Show available memory tools")
        print("  /save <file> [options]   Save session with optional analytics")
        print("  /load <file>             Load saved session")
        
        print("\n🧠 MEMORY FEATURES")
        print("─" * 50)
        print("  • Automatic conversation storage")
        print("  • Semantic memory search")
        print("  • Context reconstruction from memory")
        print("  • Document library management")
        print("  • Automatic fact extraction")
        print("  • Memory consolidation")
        
        print("\n🛠️ AVAILABLE TOOLS")
        print("─" * 50)
        print("  Memory Tools:")
        print("    • remember_fact() - Store important information")
        print("    • search_memories() - Search past conversations")
        print("    • reflect_on() - Deep reflection and analysis")
        print("    • capture_document() - Save documents to library")
        print("    • search_library() - Search document library")
        print("  File & System Tools:")
        print("    • list_files() - List directory contents")
        print("    • search_files() - Search inside files")
        print("    • read_file() - Read file contents")
        print("    • write_file() - Create/modify files")
        print("    • edit_file() - Edit files with patterns")
        print("    • execute_command() - Run shell commands")
        
        print("\n💡 TIPS")
        print("─" * 50)
        print("  • Ask about past conversations - I remember them!")
        print("  • I can reflect on topics to provide deeper insights")
        print("  • Share documents or information for me to remember")
        print("  • My memory grows and improves with each interaction")
        
        print("="*70 + "\n")

    def _show_detailed_stats(self):
        """Show detailed memory and session statistics."""
        
        print("\n📊 Memory Statistics")
        print("=" * 50)
        
        try:
            # Memory file counts
            notes_dir = self.memory_path / "notes"
            verbatim_dir = self.memory_path / "verbatim"
            library_dir = self.memory_path / "library"
            
            note_files = list(notes_dir.rglob("*.md")) if notes_dir.exists() else []
            verbatim_files = list(verbatim_dir.rglob("*.md")) if verbatim_dir.exists() else []
            library_files = list(library_dir.rglob("*.md")) if library_dir.exists() else []
            
            print(f"📝 Notes: {len(note_files)}")
            print(f"💬 Conversations: {len(verbatim_files)}")
            print(f"📚 Library Documents: {len(library_files)}")
            
            # Session stats
            messages = self.session.get_messages()
            print(f"🗨️  Current Session Messages: {len(messages)}")
            print(f"🔢 Estimated Tokens: ~{self.session.get_token_estimate():,}")
            
            # Tool stats
            print(f"🛠️  Available Tools: {len(self.session.tools)}")
            
            # Memory path info
            print(f"📁 Memory Path: {self.memory_path}")
            print(f"👤 User ID: {self.user_id}")
            print(f"📍 Location: {self.location}")
            
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
        
        print("=" * 50)

    def _show_conversation_history(self):
        """Show recent conversation history."""
        
        print("\n💬 Recent Conversation")
        print("=" * 50)
        
        try:
            messages = self.session.get_messages()
            
            # Show last 10 messages (excluding system)
            recent_messages = [m for m in messages if m.role != 'system'][-10:]
            
            if not recent_messages:
                print("No conversation history yet.")
            else:
                for msg in recent_messages:
                    if msg.role == 'user':
                        print(f"👤 You: {msg.content}")
                    elif msg.role == 'assistant':
                        print(f"🤖 Assistant: {msg.content}")
                    elif msg.role == 'tool':
                        print(f"🛠️  Tool: {msg.content[:100]}...")
                    print()
            
        except Exception as e:
            print(f"❌ Error getting history: {e}")
        
        print("=" * 50)

    def _show_memory_overview(self):
        """Show memory system overview."""
        
        print("\n🧠 Memory System Overview")
        print("=" * 50)
        
        try:
            # Check memory components
            components = [
                ("Working Memory", hasattr(self.session, 'working_memory')),
                ("Episodic Memory", hasattr(self.session, 'episodic_memory')),
                ("Semantic Memory", hasattr(self.session, 'semantic_memory')),
                ("Library Memory", hasattr(self.session, 'library')),
                ("LanceDB Storage", self.session.lancedb_storage is not None),
                ("Fact Extractor", self.session.fact_extractor is not None),
                ("Consolidation Scheduler", hasattr(self.session, 'consolidation_scheduler'))
            ]
            
            for component, available in components:
                status = "✅" if available else "❌"
                print(f"{status} {component}")
            
            # Memory directories
            print(f"\n📁 Memory Structure:")
            for subdir in ['notes', 'verbatim', 'library', 'core', 'working', 'episodic', 'semantic']:
                path = self.memory_path / subdir
                exists = "✅" if path.exists() else "📁"
                print(f"   {exists} {subdir}/")
            
        except Exception as e:
            print(f"❌ Error getting memory overview: {e}")
        
        print("=" * 50)

    def _show_available_tools(self):
        """Show available memory tools."""
        
        print("\n🛠️  Available Memory Tools")
        print("=" * 50)
        
        try:
            if hasattr(self.session, 'tools') and self.session.tools:
                for tool in self.session.tools:
                    print(f"📌 {tool.name}")
                    if hasattr(tool, 'description'):
                        print(f"   {tool.description}")
                    print()
            else:
                print("No tools available")
        
        except Exception as e:
            print(f"❌ Error getting tools: {e}")
        
        print("=" * 50)

    def _handle_save(self, filename: str, summary: bool = False, assessment: bool = False, facts: bool = False):
        """Handle /save <file> command - save current session to file with optional analytics"""
        try:
            # Ensure .json extension for consistency
            if not filename.endswith('.json'):
                filename = f"{filename}.json"
            
            print(f"💾 Saving session to {filename}...")
            
            # Get session info before saving
            messages = self.session.get_messages()
            tokens = self.session.get_token_estimate()
            
            # Generate optional analytics if requested
            analytics_generated = []
            
            if summary:
                print("   🔄 Generating summary...")
                try:
                    self.session.generate_summary(focus="key discussion points")
                    analytics_generated.append("summary")
                    print("   ✅ Summary generated")
                except Exception as e:
                    print(f"   ⚠️  Summary generation failed: {e}")
            
            if assessment:
                print("   🔄 Generating assessment...")
                try:
                    self.session.generate_assessment()
                    analytics_generated.append("assessment")
                    print("   ✅ Assessment generated")
                except Exception as e:
                    print(f"   ⚠️  Assessment generation failed: {e}")
            
            if facts:
                print("   🔄 Extracting facts...")
                try:
                    self.session.extract_facts()
                    analytics_generated.append("facts")
                    print("   ✅ Facts extracted")
                except Exception as e:
                    print(f"   ⚠️  Fact extraction failed: {e}")
            
            # Save using enhanced serialization
            self.session.save(filename)
            
            print(f"✅ Session saved successfully!")
            print(f"   📁 File: {filename}")
            print(f"   📝 Messages: {len(messages)}")
            print(f"   🔢 Tokens: ~{tokens:,}")
            print(f"   🤖 Provider: {self.provider_name}:{self.model_name}")
            print(f"   ⚙️  Settings: auto_compact={self.session.auto_compact}")
            
            if analytics_generated:
                print(f"   📊 Analytics: {', '.join(analytics_generated)}")
            
            # Note about provider restoration
            print(f"   💡 Note: Provider and tools will need to be specified when loading")
            
        except Exception as e:
            print(f"❌ Failed to save session: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()

    def _handle_load(self, filename: str):
        """Handle /load <file> command - load session from file"""
        try:
            # Ensure .json extension for consistency
            if not filename.endswith('.json'):
                filename = f"{filename}.json"
            
            # Check if file exists
            import os
            if not os.path.exists(filename):
                print(f"❌ File not found: {filename}")
                return
            
            print(f"📂 Loading session from {filename}...")
            
            # Store current session info for comparison
            old_messages = len(self.session.get_messages())
            old_tokens = self.session.get_token_estimate()
            
            # Load session with current provider and memory tools
            memory_tools = self.session._create_memory_tools()
            
            from abstractmemory.memory_session import MemorySession
            loaded_session = MemorySession.load(filename, provider=self.provider, tools=memory_tools)
            
            # Replace current session
            self.session = loaded_session
            
            # Get new session info
            new_messages = len(self.session.get_messages())
            new_tokens = self.session.get_token_estimate()
            
            print(f"✅ Session loaded successfully!")
            print(f"   📁 File: {filename}")
            print(f"   📝 Messages: {old_messages} → {new_messages}")
            print(f"   🔢 Tokens: ~{old_tokens:,} → ~{new_tokens:,}")
            print(f"   🤖 Provider: {self.provider_name}:{self.model_name} (current)")
            print(f"   ⚙️  Settings: auto_compact={self.session.auto_compact}")
            
            # Show session structure
            messages = self.session.get_messages()
            conversation_messages = [msg for msg in messages if msg.role != 'system']
            interactions = len(conversation_messages) // 2
            
            has_summary = any(msg.role == 'system' and '[CONVERSATION HISTORY]' in msg.content for msg in messages)
            if has_summary:
                print(f"   📚 History: Compacted conversation with {interactions} recent interactions")
            else:
                print(f"   💬 History: Full conversation with {interactions} interactions")
            
        except Exception as e:
            print(f"❌ Failed to load session: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()

    def _cleanup(self):
        """Cleanup before exit."""
        
        try:
            # Save embedding cache if available
            if hasattr(self.session, 'embedding_manager') and self.session.embedding_manager:
                print("   💾 Saved embedding cache")
        except Exception:
            pass

    def run(self):
        """Run the interactive REPL."""
        
        print("\n" + "="*70)
        print("🧠 AbstractMemory REPL".center(70))
        print("="*70)
        print("Type /help for commands, or just chat naturally.")
        print("I have memory tools and will remember our conversations!")
        print("="*70)
        
        try:
            while True:
                try:
                    user_input = input(f"\n👤 {self.user_id}> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if self.handle_command(user_input):
                        continue
                    
                    # Generate response using memory-enhanced session
                    start_time = time.time()
                    
                    if not self.verbose:
                        print(f"\n🤖 Thinking...")
                    
                    # AbstractCore handles everything - tools, conversation, etc.
                    response = self.session.generate(
                        prompt=user_input,
                        user_id=self.user_id,
                        location=self.location
                    )
                    
                    elapsed = time.time() - start_time
                    
                    if not self.verbose:
                        print(f"   ⏱️  Completed in {elapsed:.1f}s")
                    
                    # Display response
                    response_content = response.content if hasattr(response, 'content') else str(response)
                    print(f"\n🤖 Assistant: {response_content}")
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Use /quit to exit or continue chatting.")
                    continue
                    
                except EOFError:
                    print("\n👋 Goodbye!")
                    break
                    
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
        
        except Exception as e:
            print(f"❌ Fatal error: {e}")
        
        finally:
            self._cleanup()


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="AbstractMemory REPL - Memory-Enhanced AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python repl_clean.py
  python repl_clean.py --memory-path my_memory --user-id alice
  python repl_clean.py --provider lmstudio --model qwen/qwen3-coder-30b
  python repl_clean.py --provider ollama --model qwen3-coder:30b --verbose

Features:
  • Automatic conversation storage and indexing
  • Semantic memory search and retrieval
  • Context reconstruction from memory layers
  • Memory tools for LLM agency (remember, search, reflect)
  • Document library management
  • Automatic fact extraction and consolidation

Available Tools:
  The AI can use these tools automatically during conversation:
  
  Memory Tools:
  • remember_fact() - Store important information
  • search_memories() - Search past conversations and facts
  • reflect_on() - Deep reflection and analysis
  • capture_document() - Save documents to library
  • search_library() - Search document library
  
  File & System Tools (from AbstractCore):
  • list_files() - List directory contents with patterns
  • search_files() - Search text inside files (regex support)
  • read_file() - Read file contents with line ranges
  • write_file() - Create/modify files with error handling
  • edit_file() - Edit files using pattern matching
  • execute_command() - Run shell commands safely
        """
    )
    
    # Core arguments
    parser.add_argument('--memory-path', default='repl_memory',
                       help='Path to memory storage (default: repl_memory)')
    parser.add_argument('--user-id', default='user',
                       help='User identifier (default: user)')
    parser.add_argument('--provider', default='ollama',
                       choices=['ollama', 'lmstudio', 'openai', 'anthropic'],
                       help='LLM provider to use (default: ollama)')
    parser.add_argument('--model', default='qwen3-coder:30b',
                       help='Model to use (default: qwen3-coder:30b)')
    parser.add_argument('--location', default='terminal',
                       help='Physical/virtual location (default: terminal)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Create and run REPL
    repl = AbstractMemoryREPL(
        provider_name=args.provider,
        model=args.model,
        memory_path=args.memory_path,
        user_id=args.user_id,
        location=args.location,
        verbose=args.verbose
    )
    
    repl.run()


if __name__ == "__main__":
    main()
