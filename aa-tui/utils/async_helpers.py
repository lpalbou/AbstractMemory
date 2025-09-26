"""Async utilities for the TUI."""

import asyncio
from typing import Callable, Any, Coroutine
from prompt_toolkit.application import get_app


class AsyncTaskManager:
    """Manager for background async tasks."""

    def __init__(self):
        self.tasks = set()

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """
        Create and track an async task.

        Args:
            coro: Coroutine to execute

        Returns:
            Created task
        """
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def cancel_all(self):
        """Cancel all tracked tasks."""
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()

    async def wait_for_all(self, timeout: float = None):
        """Wait for all tasks to complete."""
        if self.tasks:
            await asyncio.wait(self.tasks, timeout=timeout)


async def run_in_background(func: Callable, *args, **kwargs) -> Any:
    """
    Run a function in the background.

    Args:
        func: Function to run
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result
    """
    loop = asyncio.get_event_loop()

    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return await loop.run_in_executor(None, func, *args, **kwargs)


def invalidate_ui():
    """Invalidate the UI to trigger a refresh."""
    try:
        app = get_app()
        if app:
            app.invalidate()
    except:
        pass  # Ignore if no app is running


async def debounce(func: Callable, delay: float = 0.1):
    """
    Debounce a function call.

    Args:
        func: Function to debounce
        delay: Delay in seconds
    """
    await asyncio.sleep(delay)
    return func()


class PeriodicTask:
    """A task that runs periodically."""

    def __init__(self, func: Callable, interval: float, *args, **kwargs):
        """
        Initialize periodic task.

        Args:
            func: Function to call periodically
            interval: Interval in seconds
            *args: Function arguments
            **kwargs: Function keyword arguments
        """
        self.func = func
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self.task = None
        self.running = False

    async def _run(self):
        """Run the periodic task."""
        while self.running:
            try:
                if asyncio.iscoroutinefunction(self.func):
                    await self.func(*self.args, **self.kwargs)
                else:
                    self.func(*self.args, **self.kwargs)
            except Exception as e:
                print(f"Error in periodic task: {e}")

            await asyncio.sleep(self.interval)

    def start(self):
        """Start the periodic task."""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._run())

    def stop(self):
        """Stop the periodic task."""
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None

    def is_running(self) -> bool:
        """Check if task is running."""
        return self.running


class ProgressTracker:
    """Track progress of long-running operations."""

    def __init__(self, total_steps: int, callback: Callable[[float, str], None] = None):
        """
        Initialize progress tracker.

        Args:
            total_steps: Total number of steps
            callback: Callback for progress updates (progress, message)
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback

    def update(self, step: int = None, message: str = ""):
        """
        Update progress.

        Args:
            step: Current step (if None, increment by 1)
            message: Progress message
        """
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1

        progress = self.current_step / self.total_steps if self.total_steps > 0 else 0.0

        if self.callback:
            self.callback(progress, message)

    def complete(self, message: str = "Complete"):
        """Mark as complete."""
        self.current_step = self.total_steps
        if self.callback:
            self.callback(1.0, message)

    @property
    def progress(self) -> float:
        """Get current progress (0.0 to 1.0)."""
        return self.current_step / self.total_steps if self.total_steps > 0 else 0.0

    @property
    def percentage(self) -> int:
        """Get current progress as percentage."""
        return int(self.progress * 100)


async def with_timeout(coro: Coroutine, timeout: float, default=None):
    """
    Run a coroutine with a timeout.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        default: Default value if timeout occurs

    Returns:
        Result or default if timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return default


def create_background_task(coro: Coroutine) -> asyncio.Task:
    """
    Create a background task that won't block the UI.

    Args:
        coro: Coroutine to run

    Returns:
        Created task
    """
    task = asyncio.create_task(coro)

    # Add error handling
    def handle_exception(task):
        try:
            task.result()
        except Exception as e:
            print(f"Background task error: {e}")

    task.add_done_callback(handle_exception)
    return task