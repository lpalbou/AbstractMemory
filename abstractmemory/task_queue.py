"""
Background Task Queue System for AbstractMemory

Manages background processes like fact extraction, consolidation, etc.
Provides visibility, retry capability, and failure tracking.
"""

import json
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from uuid import uuid4

from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    QUEUED = "queued"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskAttempt:
    """Record of a task execution attempt."""
    attempt_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: TaskStatus = TaskStatus.RUNNING
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class BackgroundTask:
    """Background task definition."""
    task_id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    request_time: datetime
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 5  # 1=highest, 10=lowest
    max_attempts: int = 3
    attempts: List[TaskAttempt] = None
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []
    
    @property
    def start_time(self) -> Optional[datetime]:
        """Get the start time of the first attempt."""
        return self.attempts[0].start_time if self.attempts else None
    
    @property
    def end_time(self) -> Optional[datetime]:
        """Get the end time of the last attempt."""
        if not self.attempts:
            return None
        last_attempt = self.attempts[-1]
        return last_attempt.end_time if last_attempt.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
    
    @property
    def total_attempts(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (self.status == TaskStatus.FAILED and 
                self.total_attempts < self.max_attempts)


class TaskQueue:
    """
    Background task queue with persistence, retry logic, and monitoring.
    """
    
    def __init__(self, queue_file: Path, notification_callback: Optional[Callable] = None):
        """
        Initialize task queue.
        
        Args:
            queue_file: Path to persist queue state
            notification_callback: Function to call for notifications
        """
        self.queue_file = queue_file
        self.notification_callback = notification_callback
        self.tasks: Dict[str, BackgroundTask] = {}
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        self._lock = threading.Lock()
        
        # Load existing tasks
        self._load_queue()
        
        # Start worker thread
        self.start_worker()
    
    def _load_queue(self):
        """Load queue state from disk."""
        try:
            if self.queue_file.exists():
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                
                for task_data in data.get('tasks', []):
                    # Convert datetime strings back to datetime objects
                    task_data['request_time'] = datetime.fromisoformat(task_data['request_time'])
                    
                    attempts = []
                    for attempt_data in task_data.get('attempts', []):
                        attempt_data['start_time'] = datetime.fromisoformat(attempt_data['start_time'])
                        if attempt_data.get('end_time'):
                            attempt_data['end_time'] = datetime.fromisoformat(attempt_data['end_time'])
                        attempt_data['status'] = TaskStatus(attempt_data['status'])
                        attempts.append(TaskAttempt(**attempt_data))
                    
                    task_data['attempts'] = attempts
                    task_data['status'] = TaskStatus(task_data['status'])
                    
                    task = BackgroundTask(**task_data)
                    self.tasks[task.task_id] = task
                
                logger.info(f"Loaded {len(self.tasks)} tasks from queue")
        
        except Exception as e:
            logger.error(f"Failed to load task queue: {e}")
    
    def _save_queue(self):
        """Save queue state to disk. Assumes caller already holds self._lock."""
        logger.debug("_save_queue called")
        try:
            logger.debug("Creating queue file directory...")
            self.queue_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("Directory created successfully")
            
            # Note: Caller must already hold self._lock for thread safety
            logger.debug("Converting tasks to serializable format...")
            # Convert to serializable format (exclude non-serializable objects)
            tasks_data = []
            for task in self.tasks.values():
                task_dict = asdict(task)
                
                # Remove non-serializable parameters
                if 'parameters' in task_dict:
                    serializable_params = {}
                    for key, value in task_dict['parameters'].items():
                        if key in ['fact_extractor', 'store_facts_callback']:
                            # Skip function objects
                            continue
                        else:
                            serializable_params[key] = value
                    task_dict['parameters'] = serializable_params
                
                # Convert datetime objects to ISO strings
                task_dict['request_time'] = task.request_time.isoformat()
                
                attempts_data = []
                for attempt in task.attempts:
                    attempt_dict = asdict(attempt)
                    attempt_dict['start_time'] = attempt.start_time.isoformat()
                    if attempt.end_time:
                        attempt_dict['end_time'] = attempt.end_time.isoformat()
                    attempt_dict['status'] = attempt.status.value
                    attempts_data.append(attempt_dict)
                
                task_dict['attempts'] = attempts_data
                task_dict['status'] = task.status.value
                tasks_data.append(task_dict)
            
            data = {'tasks': tasks_data}
            logger.debug(f"About to write {len(tasks_data)} tasks to file...")
            
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("File write completed successfully")
        
        except Exception as e:
            # Use debug level for serialization issues to avoid noise in prompt mode
            if "pickle" in str(e).lower() or "rlock" in str(e).lower():
                logger.debug(f"Task queue serialization skipped: {e}")
            else:
                logger.error(f"Failed to save task queue: {e}")
        
        logger.debug("_save_queue completed")
    
    def add_task(self, name: str, description: str, parameters: Dict[str, Any], 
                 priority: int = 5, max_attempts: int = 3) -> str:
        """
        Add a new task to the queue.
        
        Args:
            name: Task name/type
            description: Human-readable description
            parameters: Task parameters
            priority: Priority (1=highest, 10=lowest)
            max_attempts: Maximum retry attempts
            
        Returns:
            Task ID
        """
        logger.debug(f"add_task called: name={name}")
        task_id = str(uuid4())[:8]  # Short ID
        logger.debug(f"Generated task_id: {task_id}")
        
        task = BackgroundTask(
            task_id=task_id,
            name=name,
            description=description,
            parameters=parameters,
            request_time=datetime.now(),
            priority=priority,
            max_attempts=max_attempts
        )
        logger.debug(f"Created BackgroundTask object")
        
        logger.debug("About to acquire lock...")
        with self._lock:
            logger.debug("Lock acquired, adding task to queue...")
            self.tasks[task_id] = task
            logger.debug("Task added to queue, about to save...")
            self._save_queue()
            logger.debug("Queue saved successfully")
        logger.debug("Lock released")
        
        if self.notification_callback:
            logger.debug("Calling notification callback...")
            self.notification_callback(f"Task queued: {description}", "📋")
            logger.debug("Notification callback completed")
        
        logger.info(f"Added task {task_id}: {name}")
        logger.debug("add_task completed successfully")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[BackgroundTask]:
        """Get all tasks sorted by priority and request time."""
        return sorted(
            self.tasks.values(),
            key=lambda t: (t.priority, t.request_time)
        )
    
    def get_queued_tasks(self) -> List[BackgroundTask]:
        """Get tasks that are queued and ready to run."""
        return [t for t in self.get_all_tasks() if t.status == TaskStatus.QUEUED]
    
    def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed task.
        
        Args:
            task_id: Task ID to retry
            
        Returns:
            True if task was queued for retry
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        if not task.can_retry:
            return False
        
        with self._lock:
            task.status = TaskStatus.QUEUED
            self._save_queue()
        
        if self.notification_callback:
            self.notification_callback(f"Task {task_id} queued for retry", "🔄")
        
        logger.info(f"Task {task_id} queued for retry")
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.
        
        Args:
            task_id: Task ID to remove
            
        Returns:
            True if task was removed
        """
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        with self._lock:
            # Don't remove running tasks
            if task.status == TaskStatus.RUNNING:
                return False
            
            del self.tasks[task_id]
            self._save_queue()
        
        if self.notification_callback:
            self.notification_callback(f"Task {task_id} removed from queue", "🗑️")
        
        logger.info(f"Removed task {task_id}")
        return True
    
    def start_worker(self):
        """Start the background worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Task queue worker started")
    
    def stop_worker(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Task queue worker stopped")
    
    def _worker_loop(self):
        """Main worker loop that processes queued tasks."""
        while self.running:
            try:
                # Get next queued task
                queued_tasks = self.get_queued_tasks()
                if not queued_tasks:
                    time.sleep(1)  # No tasks, wait a bit
                    continue
                
                task = queued_tasks[0]  # Highest priority task
                
                # Execute task
                self._execute_task(task)
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _execute_task(self, task: BackgroundTask):
        """Execute a single task."""
        attempt_number = len(task.attempts) + 1
        attempt = TaskAttempt(
            attempt_number=attempt_number,
            start_time=datetime.now()
        )
        
        with self._lock:
            task.status = TaskStatus.RUNNING
            task.attempts.append(attempt)
            self._save_queue()
        
        if self.notification_callback:
            self.notification_callback(f"Starting {task.name} (attempt {attempt_number})", "⚙️")
        
        logger.info(f"Executing task {task.task_id}: {task.name} (attempt {attempt_number})")
        
        try:
            # Execute the actual task based on task name
            success = self._run_task_by_name(task)
            
            # Update attempt
            attempt.end_time = datetime.now()
            attempt.duration_seconds = (attempt.end_time - attempt.start_time).total_seconds()
            
            if success:
                attempt.status = TaskStatus.COMPLETED
                task.status = TaskStatus.COMPLETED
                
                if self.notification_callback:
                    self.notification_callback(f"Completed {task.name} in {attempt.duration_seconds:.1f}s", "✅")
                
                logger.info(f"Task {task.task_id} completed successfully")
            else:
                attempt.status = TaskStatus.FAILED
                attempt.error_message = "Task returned False"
                
                if task.can_retry:
                    task.status = TaskStatus.QUEUED  # Will retry
                    if self.notification_callback:
                        self.notification_callback(f"Task {task.task_id} failed, will retry", "⚠️")
                else:
                    task.status = TaskStatus.FAILED  # Max attempts reached
                    if self.notification_callback:
                        self.notification_callback(f"Task {task.task_id} failed permanently", "❌")
                
                logger.warning(f"Task {task.task_id} failed")
        
        except Exception as e:
            # Update attempt with error
            attempt.end_time = datetime.now()
            attempt.duration_seconds = (attempt.end_time - attempt.start_time).total_seconds()
            attempt.status = TaskStatus.FAILED
            attempt.error_message = str(e)
            
            if task.can_retry:
                task.status = TaskStatus.QUEUED  # Will retry
                if self.notification_callback:
                    self.notification_callback(f"Task {task.task_id} failed: {str(e)[:50]}...", "⚠️")
            else:
                task.status = TaskStatus.FAILED  # Max attempts reached
                if self.notification_callback:
                    self.notification_callback(f"Task {task.task_id} failed permanently", "❌")
            
            logger.error(f"Task {task.task_id} failed with error: {e}")
        
        finally:
            with self._lock:
                self._save_queue()
    
    def _run_task_by_name(self, task: BackgroundTask) -> bool:
        """
        Execute task based on its name/type.
        
        Args:
            task: Task to execute
            
        Returns:
            True if successful, False otherwise
        """
        if task.name == "fact_extraction":
            return self._run_fact_extraction_task(task)
        elif task.name == "consolidation":
            return self._run_consolidation_task(task)
        else:
            logger.error(f"Unknown task type: {task.name}")
            return False
    
    def _run_fact_extraction_task(self, task: BackgroundTask) -> bool:
        """Run fact extraction task."""
        try:
            # Get parameters
            params = task.parameters
            conversation_text = params.get('conversation_text')
            importance_threshold = params.get('importance_threshold', 0.7)
            
            # Function objects are not serialized, so we need to get them from the session
            # This is a limitation - tasks can only run while the session is active
            fact_extractor = params.get('fact_extractor')
            store_facts_callback = params.get('store_facts_callback')
            
            if not conversation_text:
                logger.error("Missing conversation_text for fact extraction")
                return False
            
            if not fact_extractor or not store_facts_callback:
                logger.warning("Function objects missing - task may have been loaded from disk")
                # For now, we'll skip this task if functions are missing
                # In a production system, we'd need to reconnect to the session
                return False
            
            # Run fact extraction
            facts_result = fact_extractor.extract_facts_from_conversation(
                conversation_text=conversation_text,
                importance_threshold=importance_threshold
            )
            
            if facts_result.get("error"):
                logger.error(f"Fact extraction failed: {facts_result['error']}")
                return False
            
            # Process and store facts
            memory_actions = facts_result.get("memory_actions", [])
            facts_to_store = []
            
            for action in memory_actions:
                if action.get("action") == "remember":
                    # Extract confidence from metadata if available
                    metadata = action.get("metadata", {})
                    confidence = metadata.get("confidence", action.get("importance", 0.7))
                    
                    facts_to_store.append({
                        "content": action.get("content", ""),
                        "importance": action.get("importance", 0.7),
                        "confidence": confidence,
                        "reason": action.get("reason", ""),
                        "emotion": action.get("emotion", "neutral"),
                        "timestamp": datetime.now().isoformat(),
                        "source": "automatic_extraction"
                    })
            
            # Store facts using callback
            if facts_to_store:
                store_facts_callback(facts_to_store)
                
                if self.notification_callback:
                    self.notification_callback(f"Extracted {len(facts_to_store)} new facts", "🧠")
            
            return True
            
        except Exception as e:
            logger.error(f"Fact extraction task failed: {e}")
            return False
    
    def _run_consolidation_task(self, task: BackgroundTask) -> bool:
        """Run memory consolidation task."""
        try:
            # Placeholder for consolidation logic
            # This would call the actual consolidation methods
            logger.info("Running consolidation task...")
            time.sleep(2)  # Simulate work
            return True
            
        except Exception as e:
            logger.error(f"Consolidation task failed: {e}")
            return False
