from asyncio import Task
import asyncio
from typing import Generator, Set, Coroutine, Any


_running_tasks: Set[Task[None]] = set()


def run_and_forget_task(
    call: Generator[Any, None, None] | Coroutine[Any, Any, None],
    name: str | None = None,
) -> None:
    task = asyncio.get_event_loop().create_task(call, name=name)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def cancel_all_pending_taks() -> None:
    for t in _running_tasks:
        t.cancel()
