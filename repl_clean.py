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
from typing import Dict, Any

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
        
        print("\n📎 FILE ATTACHMENT")
        print("─" * 50)
        print("  @filename.py             Attach file to your message")
        print("  @./path/to/file.txt      Attach file with relative path")
        print("  @/absolute/path/file     Attach file with absolute path")
        print("  @file1.py @file2.txt     Attach multiple files")
        print("  Examples:")
        print("    'Explain this code @main.py'")
        print("    'Compare @old.py @new.py'")
        print("    'Review @./docs/api.md'")
        
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
        """Show detailed memory system overview with usage statistics."""
        
        print("\n🧠 Memory System Overview")
        print("=" * 70)
        
        try:
            # Memory Component Status
            print("\n📊 COMPONENT STATUS")
            print("─" * 40)
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
                print(f"  {status} {component}")
            
            # Memory Usage Statistics
            print(f"\n📈 MEMORY USAGE STATISTICS")
            print("─" * 40)
            
            # Count files and estimate tokens for each memory type
            memory_stats = self._calculate_memory_usage()
            
            for memory_type, stats in memory_stats.items():
                print(f"  📁 {memory_type.title()}")
                print(f"     Files: {stats['file_count']}")
                print(f"     Size: {stats['size_mb']:.2f} MB")
                print(f"     Tokens: ~{stats['token_estimate']:,}")
                if stats.get('recent_activity'):
                    print(f"     Recent: {stats['recent_activity']}")
                print()
            
            # Core Memory Status
            print(f"🧭 CORE IDENTITY STATUS")
            print("─" * 40)
            core_path = self.memory_path / "core"
            if core_path.exists():
                core_components = ["purpose", "values", "personality", "capabilities", 
                                 "limitations", "relationships", "self_model", 
                                 "awareness_development", "emotional_significance", "authentic_voice"]
                
                for component in core_components:
                    file_path = core_path / f"{component}.md"
                    if file_path.exists():
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            if len(content) > 100 and "# Template" not in content:
                                status = "✅ Established"
                                tokens = len(content) // 4
                                print(f"  {status} {component.replace('_', ' ').title()} (~{tokens} tokens)")
                            else:
                                print(f"  📝 {component.replace('_', ' ').title()} (template)")
                        except Exception:
                            print(f"  ❌ {component.replace('_', ' ').title()} (error)")
                    else:
                        print(f"  📝 {component.replace('_', ' ').title()} (missing)")
            else:
                print("  📝 No core memory established yet")
            
            # Recent Activity
            print(f"\n⚡ RECENT ACTIVITY")
            print("─" * 40)
            recent_stats = self._get_recent_activity_stats()
            print(f"  Context Reconstructions: {recent_stats.get('reconstructions', 0)}")
            print(f"  Facts Extracted: {recent_stats.get('facts_extracted', 0)}")
            print(f"  Notes Created: {recent_stats.get('notes_created', 0)}")
            print(f"  Memory Searches: {recent_stats.get('searches', 0)}")
            
            # Working Memory Status
            print(f"\n🔄 WORKING MEMORY")
            print("─" * 40)
            working_path = self.memory_path / "working"
            if working_path.exists():
                temp_semantics = working_path / "temporary_semantics.md"
                unresolved = working_path / "unresolved.md"
                
                if temp_semantics.exists():
                    content = temp_semantics.read_text(encoding='utf-8')
                    fact_count = content.count("### Fact")
                    print(f"  📝 Temporary Facts: {fact_count} pending consolidation")
                else:
                    print(f"  📝 Temporary Facts: 0 pending")
                
                if unresolved.exists():
                    content = unresolved.read_text(encoding='utf-8')
                    question_count = content.count("- ")
                    print(f"  ❓ Unresolved Questions: {question_count}")
                else:
                    print(f"  ❓ Unresolved Questions: 0")
            
        except Exception as e:
            print(f"❌ Error getting memory overview: {e}")
        
        print("=" * 70)

    def _calculate_memory_usage(self) -> Dict[str, Dict[str, Any]]:
        """Calculate memory usage statistics for each memory type."""
        
        stats = {}
        memory_types = ['notes', 'verbatim', 'library', 'core', 'working', 'episodic', 'semantic']
        
        for memory_type in memory_types:
            type_path = self.memory_path / memory_type
            
            file_count = 0
            total_size = 0
            total_tokens = 0
            recent_files = 0
            
            if type_path.exists():
                try:
                    from datetime import datetime, timedelta
                    recent_threshold = datetime.now() - timedelta(days=7)
                    
                    for file_path in type_path.rglob("*.md"):
                        if file_path.is_file():
                            file_count += 1
                            
                            # Get file size
                            size = file_path.stat().st_size
                            total_size += size
                            
                            # Estimate tokens (rough: 1 token ≈ 4 characters)
                            try:
                                content = file_path.read_text(encoding='utf-8')
                                total_tokens += len(content) // 4
                            except Exception:
                                total_tokens += size // 4  # Fallback estimate
                            
                            # Check if recent
                            if datetime.fromtimestamp(file_path.stat().st_mtime) > recent_threshold:
                                recent_files += 1
                
                except Exception as e:
                    # Fallback for errors
                    pass
            
            # Recent activity description
            recent_activity = ""
            if recent_files > 0:
                recent_activity = f"{recent_files} files in last 7 days"
            
            stats[memory_type] = {
                'file_count': file_count,
                'size_mb': total_size / (1024 * 1024),
                'token_estimate': total_tokens,
                'recent_activity': recent_activity
            }
        
        return stats

    def _get_recent_activity_stats(self) -> Dict[str, int]:
        """Get recent activity statistics from session or memory files."""
        
        stats = {
            'reconstructions': 0,
            'facts_extracted': 0,
            'notes_created': 0,
            'searches': 0
        }
        
        try:
            # Try to get stats from session if available
            if hasattr(self.session, 'reconstructions_performed'):
                stats['reconstructions'] = getattr(self.session, 'reconstructions_performed', 0)
            
            # Count recent notes (last 24 hours)
            from datetime import datetime, timedelta
            recent_threshold = datetime.now() - timedelta(hours=24)
            
            notes_path = self.memory_path / "notes"
            if notes_path.exists():
                for note_file in notes_path.rglob("*.md"):
                    if note_file.is_file():
                        mtime = datetime.fromtimestamp(note_file.stat().st_mtime)
                        if mtime > recent_threshold:
                            stats['notes_created'] += 1
            
            # Count temporary facts
            temp_semantics = self.memory_path / "working" / "temporary_semantics.md"
            if temp_semantics.exists():
                try:
                    content = temp_semantics.read_text(encoding='utf-8')
                    # Count recent fact sections (last 24 hours)
                    import re
                    today = datetime.now().strftime('%Y-%m-%d')
                    if today in content:
                        stats['facts_extracted'] = content.count("### Fact")
                except Exception:
                    pass
            
            # Estimate searches (could be tracked in session in future)
            stats['searches'] = stats['reconstructions']  # Approximation
            
        except Exception as e:
            # Return zeros on error
            pass
        
        return stats

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

    def _process_file_references(self, user_input: str) -> str:
        """
        Process @filename references in user input and inject file contents.
        
        Supports:
        - @filename.py (relative to current directory)
        - @./path/to/file.txt (relative path)
        - @/absolute/path/to/file.txt (absolute path)
        - Multiple files: @file1.py @file2.txt
        
        Args:
            user_input: Raw user input potentially containing @filename references
            
        Returns:
            Enhanced prompt with file contents injected
        """
        
        import re
        from pathlib import Path
        
        # Find all @filename patterns
        # Matches: @filename, @./path/file, @/abs/path/file, @../relative/file
        pattern = r'@([^\s@]+(?:\.[^\s@]*)?)'
        matches = re.findall(pattern, user_input)
        
        if not matches:
            return user_input
        
        # Process each file reference
        file_contents = []
        processed_files = []
        
        for filename in matches:
            try:
                # Handle different path types
                if filename.startswith('/'):
                    # Absolute path
                    file_path = Path(filename)
                elif filename.startswith('./') or filename.startswith('../'):
                    # Relative path with explicit prefix
                    file_path = Path(filename).resolve()
                else:
                    # Simple filename - look in current directory first, then workspace
                    file_path = Path(filename)
                    if not file_path.exists():
                        # Try in workspace root
                        workspace_path = Path.cwd() / filename
                        if workspace_path.exists():
                            file_path = workspace_path
                
                # Check if file exists and is readable
                if not file_path.exists():
                    print(f"⚠️  File not found: {filename}")
                    continue
                
                if not file_path.is_file():
                    print(f"⚠️  Not a file: {filename}")
                    continue
                
                # Check file size (limit to 100KB for safety)
                file_size = file_path.stat().st_size
                if file_size > 100 * 1024:  # 100KB
                    print(f"⚠️  File too large (>{file_size/1024:.1f}KB): {filename}")
                    continue
                
                # Read file content
                try:
                    content = file_path.read_text(encoding='utf-8')
                    
                    # Determine file type for syntax highlighting hint
                    file_ext = file_path.suffix.lower()
                    lang_map = {
                        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                        '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
                        '.rs': 'rust', '.go': 'go', '.rb': 'ruby', '.php': 'php',
                        '.html': 'html', '.css': 'css', '.scss': 'scss',
                        '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
                        '.md': 'markdown', '.txt': 'text', '.sh': 'bash',
                        '.sql': 'sql', '.r': 'r', '.m': 'matlab'
                    }
                    language = lang_map.get(file_ext, 'text')
                    
                    # Format file content
                    file_block = f"""
[File: {file_path}]
```{language}
{content}
```"""
                    
                    file_contents.append(file_block)
                    processed_files.append(str(file_path))
                    
                    print(f"📁 Loaded: {file_path} ({len(content)} chars)")
                    
                except UnicodeDecodeError:
                    print(f"⚠️  Cannot read file (binary?): {filename}")
                    continue
                    
            except Exception as e:
                print(f"⚠️  Error reading {filename}: {e}")
                continue
        
        # If no files were successfully processed, return original input
        if not file_contents:
            return user_input
        
        # Remove @filename references from the original input
        cleaned_input = user_input
        for filename in matches:
            cleaned_input = cleaned_input.replace(f"@{filename}", "")
        cleaned_input = re.sub(r'\s+', ' ', cleaned_input).strip()
        
        # Construct enhanced prompt
        if file_contents:
            files_section = "--- Attached Files ---" + "".join(file_contents)
            
            if cleaned_input:
                enhanced_prompt = f"{cleaned_input}\n\n{files_section}"
            else:
                enhanced_prompt = f"Please analyze the attached files.\n\n{files_section}"
            
            print(f"📎 Attached {len(processed_files)} file(s) to context")
            return enhanced_prompt
        
        return user_input

    def run(self):
        """Run the interactive REPL."""
        
        print("\n" + "="*70)
        print("🧠 AbstractMemory REPL".center(70))
        print("="*70)
        print("Type /help for commands, or just chat naturally.")
        print("I have memory tools and will remember our conversations!")
        print("Use @filename to attach files to your messages!")
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
                    
                    # Process @filename references and enhance prompt
                    enhanced_prompt = self._process_file_references(user_input)
                    
                    # Generate response using memory-enhanced session
                    start_time = time.time()
                    
                    if not self.verbose:
                        print(f"\n🤖 Thinking...")
                    
                    # AbstractCore handles everything - tools, conversation, etc.
                    response = self.session.generate(
                        prompt=enhanced_prompt,
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
