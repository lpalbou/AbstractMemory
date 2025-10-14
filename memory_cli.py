#!/usr/bin/env python3
"""
AbstractMemory CLI - Memory-Enhanced AI Assistant

A command-line interface for AbstractMemory that provides rich, structured
conversations with comprehensive memory automation, context reconstruction,
and enhanced metadata display.

Features:
- Automatic conversation storage and indexing
- Semantic memory search and retrieval  
- Context reconstruction from memory layers
- Memory tools for LLM agency (remember, search, reflect)
- Document library management with @filename support
- Rich metadata display with tokens, timing, importance & alignment
- Automatic fact extraction and consolidation

Usage:
    python memory_cli.py
    python memory_cli.py --memory-path my_memory --name alice
    python memory_cli.py --provider lmstudio --model qwen/qwen3-coder-30b
"""

import argparse
import sys
import time
from pathlib import Path
from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)
from typing import Dict, Any

# Terminal styling
import colorama
from colorama import Style
colorama.init()  # Initialize colorama for cross-platform color support


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
                 user_id: str = "user", location: str = "terminal", verbose: bool = False, debug: bool = False, 
                 prompt_mode: bool = False):
        """Initialize the REPL with memory-enhanced session."""
        
        self.provider_name = provider_name
        self.model_name = model
        self.memory_path = Path(memory_path)
        self.user_id = user_id
        self.location = location
        self.verbose = verbose
        self.debug = debug
        self.prompt_mode = prompt_mode
        self._cleanup_done = False
        self._input_active = False  # Track if user is typing
        self._last_prompt = ""      # Store last prompt for redisplay
        self._notifications = []    # Store recent notifications
        
        # Set up logging level for debug mode
        if self.debug:
            from abstractllm.utils.structured_logging import configure_logging
            import logging
            # Configure AbstractCore logging to show debug messages on console
            configure_logging(
                console_level=logging.DEBUG,
                file_level=logging.DEBUG,
                log_dir=None,  # No file logging for now
                verbatim_enabled=True,
                console_json=False  # Human readable console output
            )
        
        # Initialize provider (suppress output in prompt mode unless debug)
        if not self.prompt_mode or self.debug:
            print(f"🧠 Initializing AbstractMemory...")
            print(f"   Memory Path: {memory_path}")
            print(f"   User ID: {user_id}")
            print(f"   Model: {model}")
            print(f"   Provider: {provider_name}")
            if self.debug:
                print(f"   Debug Mode: ENABLED")
        
        try:
            if self.debug:
                logger.debug(f"Creating LLM provider: {provider_name} with model: {model}")
            self.provider = create_llm(provider_name, model=model)
            if self.debug:
                logger.debug(f"LLM provider created successfully: {type(self.provider)}")
        except Exception as e:
            logger.error(f"Failed to create provider: {e}")
            print(f"❌ Failed to create provider: {e}")
            sys.exit(1)
        
        # Initialize embedding manager
        try:
            if self.debug:
                logger.debug("Initializing embedding manager...")
            self.embedding_manager = EmbeddingManager(model="all-minilm-l6-v2", backend="auto")
            if self.debug:
                logger.debug(f"Embedding manager initialized: {type(self.embedding_manager)}")
        except Exception as e:
            logger.warning(f"Embedding manager initialization failed: {e}")
            print(f"⚠️  Embedding manager initialization failed: {e}")
            self.embedding_manager = None
        
        # Create memory-enhanced session
        try:
            if self.debug:
                logger.debug("Creating MemorySession...")
                logger.debug(f"Memory base path: {self.memory_path}")
                logger.debug(f"Default user ID: {user_id}")
                logger.debug(f"Default location: {location}")
            
            self.session = MemorySession(
                provider=self.provider,
                system_prompt=self._create_system_prompt(),
                memory_base_path=self.memory_path,
                embedding_manager=self.embedding_manager,
                default_user_id=user_id,
                default_location=location
            )
            
            if self.debug:
                logger.debug("MemorySession created successfully")
                logger.debug(f"Session tools count: {len(self.session.tools) if hasattr(self.session, 'tools') else 'unknown'}")
                logger.debug(f"Task queue available: {hasattr(self.session, 'task_queue') and self.session.task_queue is not None}")
            
            # Set notification callback for background processes
            self.session._notification_callback = self._show_background_notification
            
            if not self.prompt_mode or self.debug:
                print(f"✅ Memory session initialized")
                
                # Show memory stats
                self._show_memory_stats()
            
        except Exception as e:
            logger.error(f"Failed to initialize memory session: {e}")
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
        
        # Parse command and arguments
        parts = user_input[1:].strip().split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
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
        
        elif cmd == 'reset':
            self._handle_reset(args)
        
        elif cmd == 'clear':
            # Clear terminal like Unix command
            import os
            os.system('clear' if os.name == 'posix' else 'cls')
            print("🧹 Terminal cleared")
        
        elif cmd == 'memory':
            self._show_memory_overview()
        
        elif cmd == 'tools':
            self._show_available_tools()
        
        elif cmd == 'facts':
            self._show_facts()
        
        elif cmd == 'unresolved':
            self._show_unresolved_questions()
        
        elif cmd == 'resolved':
            self._show_resolved_questions()
        
        elif cmd.startswith('reconstruct'):
            # Parse /reconstruct <query> command
            if len(args) == 0:
                print("❓ Usage: /reconstruct <query>")
                print("   Example: /reconstruct identity formation")
                print("   Shows the exact context that would be fed to the LLM")
            else:
                query = ' '.join(args)
                self._show_reconstruct_context(query)
        
        elif cmd.startswith('search'):
            # Parse /search <query> command
            if len(args) == 0:
                print("❓ Usage: /search <query>")
                print("   Example: /search machine learning")
                print("   Performs semantic search across all memory")
            else:
                query = ' '.join(args)
                self._show_semantic_search(query)
        
        elif cmd == 'notifications':
            self._show_notifications()
        
        elif cmd.startswith('queue'):
            # Parse /queue [task_id] [command] 
            if len(args) == 0:
                self._show_task_queue()
            elif len(args) == 1:
                self._show_task_details(args[0])
            elif len(args) == 2:
                task_id, command = args[0], args[1]
                self._handle_task_command(task_id, command)
            else:
                print("❓ Usage: /queue [task_id] [command]")
                print("   /queue                    - Show all tasks")
                print("   /queue <task_id>          - Show task details")
                print("   /queue <task_id> retry    - Retry failed task")
                print("   /queue <task_id> remove   - Remove task")
        
        elif cmd == 'test-notify':
            # Hidden test command for notifications
            self._show_background_notification("Test notification - fact extraction completed", "🧠")
            self._show_background_notification("Another test notification", "✅")
        
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
        print("  /clear                   Clear terminal screen")
        print("  /reset                   Reset conversation history")
        print("  /reset full              Reset everything - ALL memory components (with confirmation)")
        print("  /stats                   Show detailed memory statistics")
        print("  /history                 Show recent conversation")
        print("  /memory                  Show memory overview")
        print("  /tools                   Show available memory tools")
        print("  /facts                   Show extracted facts from temporary_semantics.md")
        print("  /unresolved              Show unresolved questions")
        print("  /resolved                Show resolved questions")
        print("  /reconstruct <query>     Show exact context that would be fed to LLM")
        print("  /search <query>          Semantic search across all memory")
        print("  /queue [task_id] [cmd]   Manage background task queue")
        print("  /notifications           Show recent background notifications")
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
            
            # Facts stats
            facts_count = self._count_extracted_facts()
            print(f"🧠 Extracted Facts: {facts_count}")
            
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
                
                # Count facts using the new compact format
                facts_count = self._count_extracted_facts()
                print(f"  🧠 Extracted Facts: {facts_count} pending consolidation")
                
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

    def _count_extracted_facts(self) -> int:
        """Count extracted facts from temporary_semantics.md."""
        
        try:
            temp_semantics_file = self.memory_path / "working" / "temporary_semantics.md"
            
            if not temp_semantics_file.exists():
                return 0
            
            content = temp_semantics_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            fact_count = 0
            for line in lines:
                if line.startswith('- ') and ('→' in line or ':' in line):
                    fact_count += 1
            
            return fact_count
            
        except Exception as e:
            return 0

    def _search_facts_for_query(self, query: str) -> list:
        """Search extracted facts for query-relevant terms."""
        
        try:
            temp_semantics_file = self.memory_path / "working" / "temporary_semantics.md"
            
            if not temp_semantics_file.exists():
                return []
            
            content = temp_semantics_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Convert query to lowercase for matching
            query_terms = query.lower().split()
            relevant_facts = []
            
            for line in lines:
                if line.startswith('- ') and ('→' in line or ':' in line):
                    fact = line[2:]  # Remove "- " prefix
                    fact_lower = fact.lower()
                    
                    # Check if any query term appears in the fact
                    if any(term in fact_lower for term in query_terms):
                        relevant_facts.append(fact)
            
            return relevant_facts[:5]  # Return top 5 matches
            
        except Exception as e:
            return []

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

    def _show_facts(self):
        """Show extracted facts from temporary_semantics.md."""
        
        print("\n📝 Extracted Facts")
        print("=" * 70)
        
        try:
            temp_semantics_file = self.memory_path / "working" / "temporary_semantics.md"
            
            if not temp_semantics_file.exists():
                print("No facts extracted yet. Facts appear here after conversations.")
                print("=" * 70)
                return
            
            content = temp_semantics_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            current_section = None
            fact_count = 0
            
            for line in lines:
                if line.startswith('## ') and 'id:' in line:
                    # New section header
                    current_section = line[3:]  # Remove "## "
                    print(f"\n🕒 {current_section}")
                    print("─" * 60)
                elif line.startswith('- ') and ('→' in line or ':' in line):
                    # Fact line
                    fact = line[2:]  # Remove "- "
                    fact_count += 1
                    
                    # Parse fact components
                    if '→' in fact:
                        # SPO relationship
                        parts = fact.split(' | ')
                        if len(parts) >= 4:
                            spo = parts[0]
                            importance = parts[1]
                            confidence = parts[2]
                            emotion = parts[3]
                            print(f"  🔗 {spo}")
                            print(f"     Importance: {importance} | Confidence: {confidence} | Emotion: {emotion}")
                        else:
                            print(f"  🔗 {fact}")
                    elif ':' in fact:
                        # Entity definition
                        parts = fact.split(' | ')
                        if len(parts) >= 4:
                            entity_def = parts[0]
                            importance = parts[1]
                            confidence = parts[2]
                            emotion = parts[3]
                            print(f"  📋 {entity_def}")
                            print(f"     Importance: {importance} | Confidence: {confidence} | Emotion: {emotion}")
                        else:
                            print(f"  📋 {fact}")
                    print()
            
            if fact_count == 0:
                print("No facts found in temporary_semantics.md")
            else:
                print(f"\n📊 Total Facts: {fact_count}")
            
        except Exception as e:
            print(f"❌ Error reading facts: {e}")
        
        print("=" * 70)

    def _show_unresolved_questions(self):
        """Show unresolved questions from working memory."""
        
        print("\n❓ Unresolved Questions")
        print("=" * 70)
        
        try:
            unresolved_file = self.memory_path / "working" / "unresolved.md"
            
            if not unresolved_file.exists():
                print("No unresolved questions file found.")
                print("=" * 70)
                return
            
            content = unresolved_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            question_count = 0
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('# '):
                    # Main header
                    continue
                elif line.startswith('## '):
                    # Section header
                    current_section = line[3:]
                    print(f"\n📅 {current_section}")
                    print("─" * 50)
                elif line.startswith('- '):
                    # Question item
                    question = line[2:]
                    question_count += 1
                    print(f"  {question_count}. {question}")
            
            if question_count == 0:
                print("No unresolved questions found.")
            else:
                print(f"\n📊 Total Unresolved: {question_count}")
            
        except Exception as e:
            print(f"❌ Error reading unresolved questions: {e}")
        
        print("=" * 70)

    def _show_resolved_questions(self):
        """Show resolved questions from working memory."""
        
        print("\n✅ Resolved Questions")
        print("=" * 70)
        
        try:
            resolved_file = self.memory_path / "working" / "resolved.md"
            
            if not resolved_file.exists():
                print("No resolved questions file found.")
                print("=" * 70)
                return
            
            content = resolved_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            resolution_count = 0
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('# '):
                    # Main header
                    continue
                elif line.startswith('## '):
                    # Section header
                    current_section = line[3:]
                    print(f"\n📅 {current_section}")
                    print("─" * 50)
                elif line.startswith('- '):
                    # Resolution item
                    resolution = line[2:]
                    resolution_count += 1
                    print(f"  {resolution_count}. {resolution}")
            
            if resolution_count == 0:
                print("No resolved questions found.")
            else:
                print(f"\n📊 Total Resolved: {resolution_count}")
            
        except Exception as e:
            print(f"❌ Error reading resolved questions: {e}")
        
        print("=" * 70)

    def _show_reconstruct_context(self, query: str):
        """Show the exact context that would be reconstructed for a query."""
        
        print(f"\n🧠 Context Reconstruction for: '{query}'")
        print("=" * 70)
        
        try:
            # Get the actual enhanced prompt that would be sent to the LLM
            enhanced_prompt = self.session._reconstruct_context_for_prompt(query, self.user_id, self.location)
            
            print("📋 EXACT LLM PROMPT CONTEXT")
            print("─" * 70)
            print(enhanced_prompt)
            print("─" * 70)
            
            # Now show structured breakdown
            print(f"\n📊 STRUCTURED BREAKDOWN")
            print("=" * 70)
            
            # Search for relevant conversations
            if self.session.lancedb_storage:
                print("💬 RELEVANT CONVERSATIONS")
                print("─" * 50)
                
                verbatim_results = self.session.lancedb_storage.search_all_tables(query, tables=["verbatim"], limit=3)
                conversations = verbatim_results.get("verbatim", [])
                
                if conversations:
                    for i, conv in enumerate(conversations, 1):
                        user_input = conv.get('user_input', 'No input')[:100]
                        agent_response = conv.get('agent_response', 'No response')[:150]
                        timestamp = conv.get('timestamp', 'Unknown')
                        
                        print(f"  {i}. {timestamp}")
                        print(f"     Q: {user_input}...")
                        print(f"     A: {agent_response}...")
                        print()
                else:
                    print("  No relevant conversations found")
                
                print("\n📝 RELEVANT NOTES & REFLECTIONS")
                print("─" * 50)
                
                note_results = self.session.lancedb_storage.search_notes(query, {}, limit=3)
                if note_results:
                    for i, note in enumerate(note_results, 1):
                        content = note.get('content', 'No content')[:200]
                        timestamp = note.get('timestamp', 'Unknown')
                        category = note.get('category', 'note')
                        
                        print(f"  {i}. [{category.upper()}] {timestamp}")
                        print(f"     {content}...")
                        print()
                else:
                    print("  No relevant notes found")
            
            print("\n🧠 RELEVANT FACTS")
            print("─" * 50)
            
            # Search facts for query terms
            relevant_facts = self._search_facts_for_query(query)
            if relevant_facts:
                for i, fact in enumerate(relevant_facts, 1):
                    print(f"  {i}. {fact}")
            else:
                print("  No relevant facts found")
            
            # Show token estimate
            estimated_tokens = len(enhanced_prompt) // 4
            print(f"\n📊 CONTEXT STATISTICS")
            print("─" * 50)
            print(f"  Total Characters: {len(enhanced_prompt):,}")
            print(f"  Estimated Tokens: ~{estimated_tokens:,}")
            print(f"  Query Match Quality: {'High' if len(relevant_facts) > 0 else 'Low'}")
            
        except Exception as e:
            print(f"❌ Error reconstructing context: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
        
        print("=" * 70)

    def _show_semantic_search(self, query: str):
        """Show semantic search results across all memory."""
        
        print(f"\n🔍 Semantic Search: '{query}'")
        print("=" * 70)
        
        try:
            if not self.session.lancedb_storage:
                print("❌ LanceDB storage not available - semantic search disabled")
                print("=" * 70)
                return
            
            print("🔍 SEARCHING NOTES")
            print("─" * 40)
            
            # Search notes
            note_results = self.session.lancedb_storage.search_notes(query, {}, limit=5)
            if note_results:
                for i, result in enumerate(note_results, 1):
                    content = result.get('content', 'No content')
                    # Convert LanceDB distance to similarity score (0-1, higher = better)
                    distance = result.get('_distance', 1.0)
                    similarity = max(0.0, 1.0 - distance)  # Convert distance to similarity
                    
                    # Format timestamp without milliseconds
                    raw_timestamp = result.get('timestamp', 'Unknown')
                    if raw_timestamp != 'Unknown' and hasattr(raw_timestamp, 'strftime'):
                        timestamp = raw_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(raw_timestamp, str) and '.' in raw_timestamp:
                        # Remove milliseconds from string timestamps
                        timestamp = raw_timestamp.split('.')[0]
                    else:
                        timestamp = str(raw_timestamp)
                    
                    user_id = result.get('user_id', 'Unknown')
                    file_path = result.get('file_path', '')
                    
                    # Smart content trimming - find query match and show context (2 lines)
                    trimmed_content = self._smart_trim_content(content, query, max_length=300)
                    
                    # Format file path for display (show relative path from memory base)
                    record_id = result.get('id', '')
                    display_path = self._format_file_path(file_path, record_id, raw_timestamp, user_id)
                    
                    # Single line header with all metadata
                    print(f"  {i}. {display_path} | Score: {similarity:.3f} | User: {user_id} | Time: {timestamp}")
                    
                    # Content in italic and darker grey
                    print(f"     {colorama.Style.DIM}{trimmed_content}{colorama.Style.RESET_ALL}")
                    print()
            else:
                print("  No matching notes found")
            
            print("\n💬 SEARCHING VERBATIM CONVERSATIONS")
            print("─" * 40)
            
            # Search verbatim using search_all_tables
            all_results = self.session.lancedb_storage.search_all_tables(query, tables=["verbatim"], limit=5)
            verbatim_results = all_results.get("verbatim", [])
            if verbatim_results:
                for i, result in enumerate(verbatim_results, 1):
                    user_input = result.get('user_input', 'No input')
                    agent_response = result.get('agent_response', 'No response')
                    # Convert LanceDB distance to similarity score (0-1, higher = better)
                    distance = result.get('_distance', 1.0)
                    similarity = max(0.0, 1.0 - distance)  # Convert distance to similarity
                    
                    # Format timestamp without milliseconds
                    raw_timestamp = result.get('timestamp', 'Unknown')
                    if raw_timestamp != 'Unknown' and hasattr(raw_timestamp, 'strftime'):
                        timestamp = raw_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(raw_timestamp, str) and '.' in raw_timestamp:
                        # Remove milliseconds from string timestamps
                        timestamp = raw_timestamp.split('.')[0]
                    else:
                        timestamp = str(raw_timestamp)
                    
                    user_id = result.get('user_id', 'Unknown')
                    file_path = result.get('file_path', '')
                    
                    # Smart content trimming for both user input and agent response (2 lines each)
                    trimmed_input = self._smart_trim_content(user_input, query, max_length=200)
                    trimmed_response = self._smart_trim_content(agent_response, query, max_length=200)
                    
                    # Format file path for display (show relative path from memory base)
                    record_id = result.get('id', '')
                    display_path = self._format_file_path(file_path, record_id, raw_timestamp, user_id)
                    
                    # Single line header with all metadata
                    print(f"  {i}. {display_path} | Score: {similarity:.3f} | User: {user_id} | Time: {timestamp}")
                    
                    # Content in italic and darker grey
                    print(f"     {colorama.Style.DIM}Q: {trimmed_input}{colorama.Style.RESET_ALL}")
                    print(f"     {colorama.Style.DIM}A: {trimmed_response}{colorama.Style.RESET_ALL}")
                    print()
            else:
                print("  No matching conversations found")
            
            # Show search statistics
            total_results = len(note_results or []) + len(verbatim_results or [])
            print(f"\n📊 SEARCH STATISTICS")
            print("─" * 40)
            print(f"  Notes Found: {len(note_results or [])}")
            print(f"  Conversations Found: {len(verbatim_results or [])}")
            print(f"  Total Results: {total_results}")
            
        except Exception as e:
            print(f"❌ Error performing semantic search: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
        
        print("=" * 70)

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
        
        # Prevent double cleanup
        if self._cleanup_done:
            return
        self._cleanup_done = True
        
        try:
            # Stop task queue worker first
            if hasattr(self.session, 'task_queue') and self.session.task_queue:
                try:
                    self.session.task_queue.stop_worker()
                    logger.info("Task queue worker stopped")
                except Exception as e:
                    logger.warning(f"Task queue cleanup failed: {e}")
            
            # Save embedding cache if available
            if hasattr(self.session, 'embedding_manager') and self.session.embedding_manager:
                cache_file = getattr(self.session.embedding_manager, 'cache_file', 'unknown')
                cache_stats = self.session.embedding_manager.get_cache_stats()
                cache_size = cache_stats.get('persistent_cache_size', 0)
                
                # Get cache location for display
                cache_dir = Path(cache_file).parent.name if cache_file != 'unknown' else 'unknown'
                
                # Call save_caches
                self.session.embedding_manager.save_caches()
                
                if not self.prompt_mode or self.debug:
                    print(f"💾 Saved embedding cache: {cache_size} entries (~/.abstractllm/{cache_dir}/)\n")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Cache cleanup error: {e}")

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

    def _show_background_notification(self, message: str, icon: str = "🧠"):
        """
        Show a background notification without interrupting user input.
        
        Uses terminal control sequences to display notification and restore prompt.
        """
        
        try:
            from datetime import datetime
            timestamp = datetime.now()
            
            # Store notification for /notifications command
            self._notifications.append({
                'timestamp': timestamp,
                'message': message,
                'icon': icon
            })
            
            # Keep only last 10 notifications
            if len(self._notifications) > 10:
                self._notifications = self._notifications[-10:]
            
            import sys
            
            # Show notification in terminal if interactive
            if sys.stdout.isatty():
                # Save current cursor position and clear line
                sys.stdout.write('\033[s')  # Save cursor position
                sys.stdout.write('\033[2K')  # Clear entire line
                sys.stdout.write('\r')      # Move to beginning of line
                
                # Format notification with timestamp
                time_str = timestamp.strftime("%H:%M:%S")
                
                try:
                    from colorama import Fore, Style, init
                    init(autoreset=True)
                    notification = f"{Style.DIM}{icon} [{time_str}] {message}{Style.RESET_ALL}"
                except ImportError:
                    notification = f"{icon} [{time_str}] {message}"
                
                sys.stdout.write(notification + '\n')
                
                # Restore prompt if user was typing
                if self._input_active and self._last_prompt:
                    sys.stdout.write(self._last_prompt)
                
                sys.stdout.flush()
            else:
                # For non-interactive (testing), just print
                time_str = timestamp.strftime("%H:%M:%S")
                print(f"{icon} [{time_str}] {message}")
            
        except Exception as e:
            # Fail silently to avoid disrupting the user experience
            if self.verbose:
                print(f"Notification error: {e}")

    def _show_notifications(self):
        """Show recent background notifications."""
        
        print("\n🔔 Recent Notifications")
        print("=" * 50)
        
        if not self._notifications:
            print("No recent notifications.")
        else:
            for i, notif in enumerate(reversed(self._notifications), 1):
                timestamp = notif['timestamp'].strftime("%H:%M:%S")
                icon = notif['icon']
                message = notif['message']
                print(f"  {i}. [{timestamp}] {icon} {message}")
        
        print("=" * 50)

    def _show_task_queue(self):
        """Show all tasks in the queue as a table."""
        
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n📋 Background Task Queue [{current_time}]")
        print("=" * 88)
        
        if not hasattr(self.session, 'task_queue') or not self.session.task_queue:
            print("Task queue not available.")
            print("=" * 88)
            return
        
        tasks = self.session.task_queue.get_all_tasks()
        
        if not tasks:
            print("No tasks in queue.")
            print("=" * 88)
            return
        
        # Table header with fixed-width formatting
        print(f"{'ID':<8} | {'Name':<15} | {'Status':<10} | {'Requested':<9} | {'Started':<9} | {'Ended':<9} | {'Attempts':<8}")
        print("-" * 88)
        
        # Table rows with consistent formatting
        for task in tasks:
            task_id = task.task_id[:8]  # Ensure max 8 chars
            name = (task.name[:15]).ljust(15)  # Pad to exactly 15 chars
            status = task.status.value
            
            req_time = task.request_time.strftime("%H:%M:%S")
            start_time = task.start_time.strftime("%H:%M:%S") if task.start_time else "-"
            end_time = task.end_time.strftime("%H:%M:%S") if task.end_time else "-"
            attempts = f"{task.total_attempts}/{task.max_attempts}"
            
            # Color code status with fixed width
            try:
                from colorama import Fore, Style, init
                init(autoreset=True)
                
                if task.status.value == "completed":
                    status_display = f"{Fore.GREEN}{status:<10}{Style.RESET_ALL}"
                elif task.status.value == "failed":
                    status_display = f"{Fore.RED}{status:<10}{Style.RESET_ALL}"
                elif task.status.value == "running":
                    status_display = f"{Fore.YELLOW}{status:<10}{Style.RESET_ALL}"
                else:
                    status_display = f"{status:<10}"
            except ImportError:
                status_display = f"{status:<10}"
            
            # Use fixed-width formatting for perfect alignment
            print(f"{task_id:<8} | {name} | {status_display} | {req_time:<9} | {start_time:<9} | {end_time:<9} | {attempts:<8}")
        
        print("=" * 88)
        print(f"Total tasks: {len(tasks)}")

    def _show_task_details(self, task_id: str):
        """Show detailed information about a specific task."""
        
        print(f"\n📋 Task Details: {task_id}")
        print("=" * 60)
        
        if not hasattr(self.session, 'task_queue') or not self.session.task_queue:
            print("Task queue not available.")
            print("=" * 60)
            return
        
        task = self.session.task_queue.get_task(task_id)
        if not task:
            print(f"Task {task_id} not found.")
            print("=" * 60)
            return
        
        # Basic info
        print(f"Name: {task.name}")
        print(f"Description: {task.description}")
        print(f"Status: {task.status.value}")
        print(f"Priority: {task.priority}")
        print(f"Max Attempts: {task.max_attempts}")
        print(f"Requested: {task.request_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if task.start_time:
            print(f"Started: {task.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if task.end_time:
            print(f"Ended: {task.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Parameters (sanitized)
        print(f"\nParameters:")
        for key, value in task.parameters.items():
            if key == 'conversation_text':
                print(f"  {key}: {len(str(value))} characters")
            elif key in ['fact_extractor', 'store_facts_callback']:
                print(f"  {key}: <function>")
            else:
                print(f"  {key}: {value}")
        
        # Attempts
        if task.attempts:
            print(f"\nAttempts ({len(task.attempts)}):")
            for i, attempt in enumerate(task.attempts, 1):
                duration = ""
                if attempt.duration_seconds:
                    duration = f" ({attempt.duration_seconds:.1f}s)"
                
                print(f"  {i}. {attempt.start_time.strftime('%H:%M:%S')} - {attempt.status.value}{duration}")
                if attempt.error_message:
                    print(f"     Error: {attempt.error_message}")
        
        # Actions
        print(f"\nAvailable Actions:")
        if task.can_retry:
            print(f"  /queue {task_id} retry    - Retry this task")
        if task.status.value != "running":
            print(f"  /queue {task_id} remove   - Remove this task")
        
        print("=" * 60)

    def _handle_task_command(self, task_id: str, command: str):
        """Handle task management commands."""
        
        if not hasattr(self.session, 'task_queue') or not self.session.task_queue:
            print("Task queue not available.")
            return
        
        if command == "retry":
            success = self.session.task_queue.retry_task(task_id)
            if success:
                print(f"✅ Task {task_id} queued for retry")
            else:
                print(f"❌ Cannot retry task {task_id} (not found, not failed, or max attempts reached)")
        
        elif command == "remove":
            success = self.session.task_queue.remove_task(task_id)
            if success:
                print(f"✅ Task {task_id} removed from queue")
            else:
                print(f"❌ Cannot remove task {task_id} (not found or currently running)")
        
        else:
            print(f"❌ Unknown command: {command}")
            print("Available commands: retry, remove")

    def _handle_reset(self, args: list):
        """Handle reset commands."""
        
        if len(args) == 0:
            # Basic reset - conversation history only (no confirmation needed)
            self.session.clear_history(keep_system=True)
            print("🔄 Conversation history reset (memory preserved)")
                
        elif len(args) == 1 and args[0] == 'full':
            # Full reset - everything (still needs confirmation due to destructive nature)
            print("🚨 FULL RESET - This will delete EVERYTHING:")
            print("   • All conversation history")
            print("   • All memory components (notes, verbatim, semantic, episodic)")
            print("   • All library documents")
            print("   • All working memory")
            print("   • All core identity files")
            print("   • Embedding cache")
            print("   • LanceDB database")
            print()
            print("   ⚠️  THIS CANNOT BE UNDONE!")
            print("   Type 'DELETE' to confirm, or anything else to cancel:")
            
            confirmation = input("   > ").strip()
            if confirmation == "DELETE":
                self._perform_full_reset()
            else:
                print("❌ Full reset cancelled")
                
        else:
            print("❌ Invalid reset command. Use:")
            print("   /reset       - Reset conversation history")
            print("   /reset full  - Reset everything (requires DELETE confirmation)")

    def _perform_full_reset(self):
        """Perform a complete system reset."""
        
        import shutil
        
        try:
            print("🧹 Starting full reset...")
            
            # 1. Clear conversation history
            self.session.clear_history(keep_system=False)
            print("   ✅ Conversation history cleared")
            
            # 2. Clear embedding cache
            if hasattr(self.session, 'embedding_manager') and self.session.embedding_manager:
                try:
                    self.session.embedding_manager.clear_cache()
                    print("   ✅ Embedding cache cleared")
                except Exception as e:
                    print(f"   ⚠️  Embedding cache clear failed: {e}")
            
            # 3. Delete memory directory
            memory_path = self.session.memory_base_path
            if memory_path.exists():
                shutil.rmtree(memory_path)
                print(f"   ✅ Memory directory deleted: {memory_path}")
            
            # 4. Reinitialize memory components
            print("   🔄 Reinitializing memory components...")
            self.session._initialize_memory_components()
            print("   ✅ Memory components reinitialized")
            
            print()
            print("🎉 Full reset complete! Starting fresh with clean memory.")
            print("   All previous conversations, memories, and data have been deleted.")
            
        except Exception as e:
            print(f"❌ Full reset failed: {e}")
            print("   Some components may not have been reset properly.")
            if self.verbose:
                import traceback
                traceback.print_exc()

    def _display_enhanced_response(self, response, elapsed_time: float):
        """
        Display enhanced response with rich metadata and visual formatting.
        
        Args:
            response: The response from MemorySession (MemoryResponse or GenerateResponse)
            elapsed_time: Time taken to generate the response
        """
        
        try:
            if self.debug:
                logger.debug(f"Starting response display, response type: {type(response)}")
                logger.debug(f"Response attributes: {dir(response) if hasattr(response, '__dict__') else 'no attributes'}")
            
            from colorama import Fore, Style, init
            init(autoreset=True)  # Auto-reset colors after each print
            
            if self.debug:
                logger.debug("Colorama initialized")
            
            from abstractmemory.memory_response_models import MemoryResponse
            
            if self.debug:
                logger.debug(f"MemoryResponse imported, checking if response is instance: {isinstance(response, MemoryResponse)}")
            
            # Extract response content and metadata
            if isinstance(response, MemoryResponse):
                if self.debug:
                    logger.debug("Processing MemoryResponse - structured response")
                # Structured response - rich display
                content = response.answer
                has_structured_data = True
                if self.debug:
                    logger.debug(f"Answer content length: {len(content) if content else 0}")
                    logger.debug(f"Has experiential_note: {bool(response.experiential_note)}")
                    logger.debug(f"Memory actions count: {len(response.memory_actions) if response.memory_actions else 0}")
                    logger.debug(f"Unresolved questions count: {len(response.unresolved_questions) if response.unresolved_questions else 0}")
                
                # Calculate token estimates (try to get accurate counts)
                try:
                    # Try to get accurate token counts from AbstractCore
                    if hasattr(self.session, 'messages') and self.session.messages:
                        # Estimate input tokens from conversation history
                        total_chars = sum(len(str(msg.content)) for msg in self.session.messages[-10:])  # Last 10 messages
                        input_tokens = total_chars // 4  # Rough chars-to-tokens conversion
                    else:
                        input_tokens = 0
                    
                    # Better output token estimation
                    output_tokens = len(content) // 4  # Characters to tokens approximation
                    
                except Exception:
                    # Fallback to word-based estimation
                    input_tokens = len(self.session.messages) * 50 if hasattr(self.session, 'messages') else 0
                    output_tokens = len(content.split()) * 1.3
                
                # Extract metadata
                importance = response.emotional_resonance.importance if response.emotional_resonance else 0.0
                alignment = response.emotional_resonance.alignment_with_values if response.emotional_resonance else 0.0
                memory_actions_count = len(response.memory_actions) if response.memory_actions else 0
                has_note = bool(response.experiential_note and response.experiential_note.strip())
                unresolved_count = len(response.unresolved_questions) if response.unresolved_questions else 0
                
                # Try to get tool execution count from AbstractCore response
                tools_executed = 0
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tools_executed = len(response.tool_calls)
                elif hasattr(response, 'metadata') and response.metadata:
                    tools_executed = response.metadata.get('tools_executed', 0)
                # If we can't get it from response, estimate from memory actions (rough approximation)
                elif memory_actions_count > 0:
                    tools_executed = memory_actions_count  # Rough estimate
                
            else:
                # Legacy GenerateResponse - basic display
                content = response.content if hasattr(response, 'content') else str(response)
                has_structured_data = False
                input_tokens = 0
                output_tokens = len(content.split()) * 1.3
                importance = 0.0
                alignment = 0.0
                memory_actions_count = 0
                has_note = False
                unresolved_count = 0
                tools_executed = 0
            
            # Main response display
            print(f"\n🤖 {Fore.CYAN}Assistant:{Style.RESET_ALL} {content}")
            
            # Enhanced metadata line (grey italic style)
            if has_structured_data:
                # Generate interaction ID (timestamp-based)
                from datetime import datetime
                interaction_id = datetime.now().strftime("%H%M%S")
                
                # Calculate tokens per second
                tokens_per_sec = output_tokens / elapsed_time if elapsed_time > 0 else 0
                
                # Create metadata components with color coding
                metadata_parts = [
                    f"id:{interaction_id}",
                    f"in:{int(input_tokens)}tk",
                    f"out:{int(output_tokens)}tk", 
                    f"{tokens_per_sec:.1f}tk/s",
                    f"⚡{importance:.1f}" if importance > 0.7 else f"imp:{importance:.1f}",
                    self._format_alignment_indicator(alignment),
                ]
                
                # Add optional indicators
                if tools_executed > 0:
                    metadata_parts.append(f"🔧{tools_executed}")  # Tools executed
                if memory_actions_count > 0:
                    metadata_parts.append(f"📝{memory_actions_count}")  # Memory actions
                if has_note:
                    metadata_parts.append("💭note")  # Experiential note
                if unresolved_count > 0:
                    metadata_parts.append(f"❓{unresolved_count}")  # Unresolved questions
                
                # Display metadata line in grey italic
                metadata_line = " | ".join(metadata_parts)
                print(f"{Style.DIM}\033[3m{metadata_line}\033[0m{Style.RESET_ALL}")
                print()  # Add newline after stats line
                
                # Optional: Show experiential note if present and verbose mode
                if has_note and self.verbose and response.experiential_note:
                    note_preview = response.experiential_note[:100] + "..." if len(response.experiential_note) > 100 else response.experiential_note
                    print(f"{Style.DIM}\033[3m💭 {note_preview}\033[0m{Style.RESET_ALL}")
                
                # Optional: Show memory actions in verbose mode
                if memory_actions_count > 0 and self.verbose and response.memory_actions:
                    for i, action in enumerate(response.memory_actions[:2]):  # Show max 2 actions
                        action_desc = f"{action.action}"
                        if hasattr(action, 'content') and action.content:
                            content_preview = action.content[:50] + "..." if len(action.content) > 50 else action.content
                            action_desc += f": {content_preview}"
                        print(f"{Style.DIM}\033[3m📝 {action_desc}\033[0m{Style.RESET_ALL}")
                    
                    if len(response.memory_actions) > 2:
                        print(f"{Style.DIM}\033[3m📝 ... and {len(response.memory_actions) - 2} more actions\033[0m{Style.RESET_ALL}")
                    
            else:
                # Basic metadata for non-structured responses
                tokens_per_sec = output_tokens / elapsed_time if elapsed_time > 0 else 0
                metadata_line = f"out:{int(output_tokens)}tk | {tokens_per_sec:.1f}tk/s | legacy"
                print(f"{Style.DIM}\033[3m{metadata_line}\033[0m{Style.RESET_ALL}")
                print()  # Add newline after stats line
                
        except Exception as e:
            # Fallback to simple display if anything goes wrong
            content = response.content if hasattr(response, 'content') else str(response)
            print(f"\n🤖 Assistant: {content}")
            if self.verbose:
                print(f"Display error: {e}")

    def _format_alignment_indicator(self, alignment: float) -> str:
        """Format value alignment with visual indicators."""
        
        if alignment >= 0.8:
            return f"🟢{alignment:.1f}"  # Strong positive alignment
        elif alignment >= 0.5:
            return f"🟡{alignment:.1f}"  # Moderate alignment  
        elif alignment >= 0.0:
            return f"🟠{alignment:.1f}"  # Weak alignment
        else:
            return f"🔴{alignment:.1f}"  # Negative alignment

    def _smart_trim_content(self, content: str, query: str, max_length: int = 300) -> str:
        """
        Smart content trimming that finds query matches and shows context.
        
        Args:
            content: The content to trim
            query: The search query to find matches for
            max_length: Maximum length of trimmed content
            
        Returns:
            Trimmed content with context around query matches
        """
        
        if not content or len(content) <= max_length:
            return content
        
        # Split content into sentences
        import re
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return content[:max_length] + "..."
        
        # Look for query terms in sentences (case insensitive)
        query_terms = query.lower().split()
        best_match_idx = -1
        best_match_score = 0
        
        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            # Count how many query terms appear in this sentence
            match_score = sum(1 for term in query_terms if term in sentence_lower)
            if match_score > best_match_score:
                best_match_score = match_score
                best_match_idx = i
        
        if best_match_idx >= 0 and best_match_score > 0:
            # Found a matching sentence - show context around it
            start_idx = max(0, best_match_idx - 1)  # Previous sentence
            end_idx = min(len(sentences), best_match_idx + 2)  # Next sentence
            
            context_sentences = sentences[start_idx:end_idx]
            context_text = '. '.join(context_sentences)
            
            if len(context_text) <= max_length:
                return context_text + "."
            else:
                # If context is still too long, just use the matching sentence
                matching_sentence = sentences[best_match_idx]
                if len(matching_sentence) <= max_length:
                    return matching_sentence + "."
                else:
                    return matching_sentence[:max_length] + "..."
        
        # No query match found - use 40% prefix approach
        prefix_length = int(max_length * 0.4)
        return content[:prefix_length] + "..." + content[-(max_length - prefix_length - 3):]

    def _format_file_path(self, file_path: str, record_id: str = "", timestamp=None, user_id: str = "") -> str:
        """
        Format file path for display in search results.
        
        Args:
            file_path: Full or relative file path
            record_id: Record ID to help reconstruct path if missing
            timestamp: Timestamp to help reconstruct path if missing
            user_id: User ID to help reconstruct path if missing
            
        Returns:
            Clean, readable file path for display
        """
        if not file_path:
            # Try to reconstruct the file path from available metadata
            reconstructed_path = self._reconstruct_file_path(record_id, timestamp, user_id)
            if reconstructed_path:
                file_path = reconstructed_path
            else:
                return "📝 (memory record - no file path)"
        
        # Convert to Path object for easier manipulation
        from pathlib import Path
        path = Path(file_path)
        
        # If it's an absolute path, try to make it relative to memory base
        if path.is_absolute():
            try:
                memory_base = self.session.memory_base_path
                if memory_base and path.is_relative_to(memory_base):
                    path = path.relative_to(memory_base)
            except (AttributeError, ValueError):
                # If relative_to fails, just use the filename and parent
                path = Path(path.parent.name) / path.name
        
        # Clean up the path display
        path_str = str(path)
        
        # Replace common prefixes with shorter versions and emojis
        replacements = {
            'repl_memory/notes/': '📝 notes/',
            'repl_memory/verbatim/': '💬 verbatim/',
            'repl_memory/working/': '🧠 working/',
            'repl_memory/core/': '🎯 core/',
            'repl_memory/episodic/': '📚 episodic/',
            'repl_memory/semantic/': '🧬 semantic/',
            'repl_memory/people/': '👥 people/',
            'repl_memory/library/': '📖 library/',
            'notes/': '📝 notes/',
            'verbatim/': '💬 verbatim/',
            'working/': '🧠 working/',
            'core/': '🎯 core/',
            'episodic/': '📚 episodic/',
            'semantic/': '🧬 semantic/',
            'people/': '👥 people/',
            'library/': '📖 library/',
        }
        
        for old, new in replacements.items():
            if path_str.startswith(old):
                return new + path_str[len(old):]
        
        return path_str

    def _reconstruct_file_path(self, record_id: str, timestamp, user_id: str) -> str:
        """
        Try to reconstruct file path from record metadata.
        
        Args:
            record_id: The record ID (e.g., "note_20251014_181431")
            timestamp: The timestamp object or string
            user_id: The user ID
            
        Returns:
            Reconstructed file path or empty string if not possible
        """
        if not record_id:
            return ""
        
        try:
            # Parse timestamp for date components
            if hasattr(timestamp, 'strftime'):
                date_str = timestamp.strftime('%Y/%m/%d')
                time_str = timestamp.strftime('%H_%M_%S')
            elif isinstance(timestamp, str):
                # Try to parse string timestamp
                from datetime import datetime
                if '.' in timestamp:
                    timestamp = timestamp.split('.')[0]  # Remove microseconds
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y/%m/%d')
                    time_str = dt.strftime('%H_%M_%S')
                except:
                    return ""
            else:
                return ""
            
            # Reconstruct based on record ID pattern
            if record_id.startswith('note_') and user_id and user_id != 'unknown':
                # Experiential note pattern: notes/2025/10/14/17_51_23_experiential_note_88749691.md
                if '_' in record_id:
                    parts = record_id.split('_')
                    if len(parts) >= 4:  # note_laurent_20251014_175123_88749691
                        note_id = parts[-1] if len(parts) > 4 else "unknown"
                        return f"notes/{date_str}/{time_str}_experiential_note_{note_id}.md"
            elif record_id.startswith('verbatim_'):
                # Verbatim pattern: verbatim/laurent/2025-10-14.md
                if timestamp and hasattr(timestamp, 'strftime'):
                    date_file = timestamp.strftime('%Y-%m-%d')
                    return f"verbatim/{user_id}/{date_file}.md"
            
            # If we can't reconstruct, return empty
            return ""
            
        except Exception:
            return ""

    def run_single_prompt(self, prompt: str):
        """
        Execute a single prompt and wait for all background processes to complete.
        
        Args:
            prompt: The prompt to execute
        """
        
        # Only show prompt execution header in debug mode
        if self.debug:
            print(f"🧠 Executing prompt: {prompt}")
            print("=" * 70)
        
        try:
            if self.debug:
                print(f"[DEBUG] Starting single prompt execution: {prompt}")
                print(f"[DEBUG] Session available: {self.session is not None}")
                print(f"[DEBUG] Provider available: {self.provider is not None}")
            
            # Handle commands first
            if prompt.startswith('/'):
                if self.debug:
                    logger.debug(f"Processing command: {prompt}")
                if self.handle_command(prompt):
                    if self.debug:
                        logger.debug("Command processed successfully")
                    # Wait for background processes if it's a queue-related command
                    if 'queue' in prompt:
                        if self.debug:
                            logger.debug("Queue command detected, waiting for background processes")
                        self._wait_for_background_processes()
                    return
            
            # Process @filename references and enhance prompt
            if self.debug:
                logger.debug("Processing file references...")
            enhanced_prompt = self._process_file_references(prompt)
            if self.debug:
                logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} chars")
                if enhanced_prompt != prompt:
                    logger.debug("File references were processed and injected")
            
            # Generate response using memory-enhanced session
            start_time = time.time()
            
            # Only show "Thinking..." in debug mode
            if self.debug:
                print(f"\n🤖 Thinking...")
                print(f"[DEBUG] Starting LLM generation...")
                print(f"[DEBUG] User ID: {self.user_id}")
                print(f"[DEBUG] Location: {self.location}")
                print(f"[DEBUG] Enhanced prompt preview: {enhanced_prompt[:200]}...")
            
            # AbstractCore handles everything - tools, conversation, etc.
            response = self.session.generate(
                prompt=enhanced_prompt,
                user_id=self.user_id,
                location=self.location
            )
            
            if self.debug:
                logger.debug(f"LLM generation completed, response type: {type(response)}")
                logger.debug(f"Response has content: {hasattr(response, 'content') or hasattr(response, 'answer')}")
                logger.debug("About to calculate elapsed time and display response...")
            
            elapsed = time.time() - start_time
            if self.debug:
                logger.debug(f"Elapsed time calculated: {elapsed:.1f}s")
                print(f"   ⏱️  Completed in {elapsed:.1f}s")
            
            # Display enhanced response with metadata
            if self.debug:
                logger.debug("Displaying enhanced response...")
            self._display_enhanced_response(response, elapsed)
            
            # Wait for background processes to complete (silently unless debug)
            if self.debug:
                print(f"\n⏳ Waiting for background processes...")
                logger.debug("Starting background process wait...")
            self._wait_for_background_processes()
            
            # Show final queue status only in debug mode
            if self.debug:
                print(f"\n📋 Final Task Queue Status:")
                logger.debug("Showing final task queue status...")
                self._show_task_queue()
            
        except Exception as e:
            logger.error(f"Error executing prompt: {e}")
            print(f"❌ Error executing prompt: {e}")
            if self.verbose or self.debug:
                import traceback
                traceback.print_exc()
        
        finally:
            if self.debug:
                logger.debug("Starting cleanup...")
            self._cleanup()

    def _wait_for_background_processes(self, max_wait_seconds: int = None):
        """
        Wait for background processes (like fact extraction) to complete.
        
        Args:
            max_wait_seconds: Maximum time to wait for processes (None = no timeout)
        """
        
        if self.debug:
            logger.debug("_wait_for_background_processes called")
        
        if not hasattr(self.session, 'task_queue') or not self.session.task_queue:
            if self.debug:
                logger.debug("No task queue available, returning immediately")
            return
        
        import time
        
        start_wait = time.time()
        last_status_check = 0
        
        while max_wait_seconds is None or time.time() - start_wait < max_wait_seconds:
            # Get current tasks
            tasks = self.session.task_queue.get_all_tasks()
            if self.debug:
                logger.debug(f"Retrieved {len(tasks)} tasks from queue")
            
            # Check if any tasks are still running or queued
            active_tasks = [t for t in tasks if t.status.value in ['queued', 'running']]
            if self.debug:
                logger.debug(f"Found {len(active_tasks)} active tasks")
            
            if not active_tasks:
                if self.debug:
                    logger.debug("No active tasks found, breaking wait loop")
                    print(f"✅ All background processes completed")
                break
            
            # Show status every 10 seconds (only in debug mode)
            if time.time() - last_status_check > 10:
                if self.debug:
                    running_count = len([t for t in active_tasks if t.status.value == 'running'])
                    queued_count = len([t for t in active_tasks if t.status.value == 'queued'])
                    print(f"   ⏳ Waiting... {running_count} running, {queued_count} queued")
                last_status_check = time.time()
            
            time.sleep(1)  # Check every second
        
        # Final check
        tasks = self.session.task_queue.get_all_tasks()
        active_tasks = [t for t in tasks if t.status.value in ['queued', 'running']]
        
        if active_tasks:
            if max_wait_seconds is not None and self.debug:
                print(f"⚠️  Timeout: {len(active_tasks)} tasks still active after {max_wait_seconds}s")
            elif self.debug:
                # This shouldn't happen since we only break when no active tasks
                print(f"⚠️  {len(active_tasks)} tasks still active")
        else:
            elapsed_wait = time.time() - start_wait
            if self.debug:
                print(f"✅ All processes completed in {elapsed_wait:.1f}s")

    def run(self):
        """Run the interactive REPL."""
        
        print("\n" + "="*70)
        print("🧠 AbstractMemory REPL".center(70))
        print("="*70)
        print("Type /help for commands, or just chat naturally.")
        print("I have memory tools and will remember our conversations!")
        print("Use @filename to attach files to your messages!")
        print("Rich metadata display shows tokens, timing, importance & alignment!")
        print("="*70)
        
        try:
            while True:
                try:
                    # Set up input tracking
                    prompt = f"\n👤 {self.user_id}> "
                    self._last_prompt = prompt
                    self._input_active = True
                    
                    user_input = input(prompt).strip()
                    self._input_active = False
                    
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
                    
                    # Display enhanced response with metadata
                    self._display_enhanced_response(response, elapsed)
                    
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
  python memory_cli.py
  python memory_cli.py --memory-path my_memory --name alice
  python memory_cli.py --provider lmstudio --model qwen/qwen3-coder-30b
  python memory_cli.py --provider ollama --model qwen3-coder:30b --verbose

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
    parser.add_argument('--name', default='user',
                       help='User name for conversation (default: user)')
    parser.add_argument('--provider', default='ollama',
                       choices=['ollama', 'lmstudio', 'mlx', 'huggingface', 'openai', 'anthropic'],
                       help='LLM provider to use (default: ollama)')
    parser.add_argument('--model', default='qwen3-coder:30b',
                       help='Model to use (default: qwen3-coder:30b)')
    parser.add_argument('--location', default='terminal',
                       help='Physical/virtual location (default: terminal)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug logging (shows detailed step-by-step execution)')
    parser.add_argument('--prompt', type=str,
                       help='Execute a single prompt and exit (useful for testing)')
    
    args = parser.parse_args()
    
    # Create and run REPL
    repl = AbstractMemoryREPL(
        provider_name=args.provider,
        model=args.model,
        memory_path=args.memory_path,
        user_id=args.name,  # Map --name to user_id internally
        location=args.location,
        verbose=args.verbose,
        debug=args.debug,
        prompt_mode=bool(args.prompt)  # Enable prompt mode if --prompt is provided
    )
    
    # Handle single prompt execution or interactive mode
    if args.prompt:
        repl.run_single_prompt(args.prompt)
    else:
        repl.run()


if __name__ == "__main__":
    main()
