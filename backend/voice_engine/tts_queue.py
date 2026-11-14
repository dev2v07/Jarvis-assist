"""One-speaker-at-a-time TTS queue for streamed assistant replies."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable


class TTSQueue:
    def __init__(self, speak: Callable[[str], None], on_error: Callable[[Exception], None] | None = None):
        self._speak = speak
        self._on_error = on_error
        self._items: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="jarvis-tts-queue", daemon=True)
        self._worker.start()

    def put(self, text: str) -> None:
        text = " ".join(str(text).split()).strip()
        if text and not self._stop.is_set():
            self._items.put(text)

    def put_latest(self, text: str) -> None:
        """Keep the currently playing item, but discard stale pending speech."""
        while True:
            try:
                self._items.get_nowait()
                self._items.task_done()
            except queue.Empty:
                break
        self.put(text)

    def wait_idle(self, timeout: float = 60.0) -> bool:
        finished = threading.Event()
        self._items.put(None)
        # Sentinel is consumed only after all prior speech jobs.
        def wait_for_sentinel():
            finished.set()
        self._items.put((finished, wait_for_sentinel))  # type: ignore[arg-type]
        return finished.wait(timeout)

    def close(self) -> None:
        self._stop.set()
        self._items.put(None)
        if self._worker.is_alive() and threading.current_thread() is not self._worker:
            self._worker.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._items.get()
            if item is None:
                self._items.task_done()
                continue
            if isinstance(item, tuple):
                event, callback = item
                callback()
                event.set()
                self._items.task_done()
                continue
            try:
                self._speak(item)
            except Exception as error:
                if self._on_error is not None:
                    self._on_error(error)
            finally:
                self._items.task_done()
