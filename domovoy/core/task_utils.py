import asyncio
from asyncio import Task
from collections.abc import Coroutine
from typing import Any

_running_tasks: set[Task[None]] = set()


def run_and_forget_task(
    call: Coroutine[Any, Any, None],
    name: str | None = None,
) -> None:
    task = asyncio.get_event_loop().create_task(call, name=name)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def cancel_all_pending_taks() -> None:
    for t in _running_tasks:
        t.cancel()
