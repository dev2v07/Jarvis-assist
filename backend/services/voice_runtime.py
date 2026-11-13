"""Runtime bridge for Jarvis wake-word, commands and conversational voice."""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
import importlib.util
import tempfile
import wave
from pathlib import Path

from services.response_router import ResponseRouter
from voice_engine.tts_queue import TTSQueue


class VoiceRuntime:
    """Own the microphone lifecycle instead of leaving it to legacy scripts."""

    WAKE_WORDS = (
        "jarvis", "джарвис", "жарвис", "дарвис", "зарвис", "джар из",
        "зарбис", "нарвес", "диарвис", "завис", "зарес", "червис",
        "джервис", "джармис", "дервис", "джарлис", "джаррис", "джарбис",
    )
    ACK_FILES = {
        "hello": "К вашим услугам сэр.wav",
        "thanks": "Да сэр.wav",
        "off": "Отключаю питание.wav",
        "shutdown": "Отключаю питание.wav",
        "reboot": "Начинаю диагностику системы.wav",
    }
    COMMAND_WAVS = {
        "open_telegram": "Запрос выполнен сэр.wav",
        "open_browser": "Запрос выполнен сэр.wav",
        "open_google": "Запрос выполнен сэр.wav",
        "open_youtube": "Запрос выполнен сэр.wav",
        "open_discord": "Запрос выполнен сэр.wav",
        "open_steam": "Запрос выполнен сэр.wav",
        "open_music_service": "Мы подключены и готовы.wav",
        "music": "Мы подключены и готовы.wav",
        "music_next": "Запрос выполнен сэр.wav",
        "music_prev": "Запрос выполнен сэр.wav",
        "music_off": "Да сэр(второй).wav",
        "music_save": "Сохранить его в центральной базе данных Stark Industries.wav",
        "sound_on": "Включилось аварийное резервное питание.wav",
        "sound_off": "Отключаю питание.wav",
        "gaming_mode_on": "Мы подключены и готовы.wav",
        "gaming_mode_off": "Мы работаем над проектом сэр 2.wav",
        "switch_to_headphones": "Запрос выполнен сэр.wav",
        "switch_to_dynamics": "Запрос выполнен сэр.wav",
        "weather": "Проверка завершена.wav",
        "currency_dollar": "Проверка завершена.wav",
        "google_search": "Запрос выполнен сэр.wav",
        "show_desktop": "Да сэр(второй).wav",
        "close_window": "Да сэр(второй).wav",
        "screenshot": "Сканирование макета завершено.wav",
        "shutdown": "Отключаю питание.wav",
        "reboot": "Я перезагрузился сэр.wav",
    }

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.voice_dir = self.base_dir / "voice_engine" / "sound"
        self.vosk_model_dir = self.base_dir / "voice_engine" / "model_small"
        self._device_index = -1
        self._enabled = False
        self._microphone_enabled = True
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._state_lock = threading.Lock()
        self._last_transcript = ""
        self._last_response = ""
        self._last_error = ""
        self._tts_available = importlib.util.find_spec("TTS") is not None
        self._phase = "выключен"
        self._follow_up_until = 0.0
        self._speaking = threading.Event()
        self._conversation_queue: queue.Queue[str | None] = queue.Queue(maxsize=4)
        self._conversation_thread: threading.Thread | None = None
        self._conversation_history: list[dict[str, str]] = []
        self._response_router = ResponseRouter()
        self._tts_queue: TTSQueue | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_device(self, index: int) -> None:
        self._device_index = int(index)
        if self._enabled:
            self.stop()
            self.start()

    def start(self) -> dict:
        if self._enabled and self._thread and self._thread.is_alive():
            self._ensure_conversation_worker()
            return self.status()
        self._last_error = ""
        self._phase = "запускается"
        self._microphone_enabled = True
        self._stop.clear()
        self._enabled = True
        self._thread = threading.Thread(target=self._run, name="jarvis-voice", daemon=True)
        self._thread.start()
        self._ensure_conversation_worker()
        if self._tts_queue is None:
            from voice_engine.tts import speak

            self._tts_queue = TTSQueue(speak)
        return self.status()

    def _ensure_conversation_worker(self) -> None:
        if self._conversation_thread and self._conversation_thread.is_alive():
            return
        self._conversation_thread = threading.Thread(
            target=self._conversation_loop,
            name="jarvis-conversation",
            daemon=True,
        )
        self._conversation_thread.start()

    def stop(self) -> dict:
        self._enabled = False
        self._phase = "выключен"
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3)
        self._thread = None
        try:
            self._conversation_queue.put_nowait(None)
        except queue.Full:
            pass
        conversation_thread = self._conversation_thread
        if (
            conversation_thread
            and conversation_thread.is_alive()
            and conversation_thread is not threading.current_thread()
        ):
            conversation_thread.join(timeout=3)
        self._conversation_thread = None
        if self._tts_queue is not None:
            self._tts_queue.close()
            self._tts_queue = None
        self._phase = "выключен"
        return self.status()

    def set_microphone_enabled(self, enabled: bool) -> dict:
        """Allow the listener to stay alive while audio capture is muted."""
        self._microphone_enabled = bool(enabled)
        if self._enabled:
            self._phase = "слушаю" if self._microphone_enabled else "микрофон выключен"
        return self.status()

    def status(self) -> dict:
        thread = self._thread
        return {
            "enabled": bool(self._enabled),
            "listening": bool(self._enabled and thread and thread.is_alive()),
            "microphone_enabled": bool(self._microphone_enabled),
            "microphone_index": self._device_index,
            "last_transcript": self._last_transcript,
            "last_response": self._last_response,
            "last_error": self._last_error,
            "tts_available": self._tts_available,
            "phase": self._phase,
            "conversation_worker": bool(
                self._conversation_thread and self._conversation_thread.is_alive()
            ),
            "conversation_queue_size": self._conversation_queue.qsize(),
        }

    def _run(self) -> None:
        try:
            from voice_engine.stt import FasterWhisperRecognizer
            from voice_engine.vad import SileroVAD

            if FasterWhisperRecognizer.available() and SileroVAD.available():
                self._run_vad_whisper(FasterWhisperRecognizer(), SileroVAD())
                return
        except Exception as error:
            self._last_error = f"vad/whisper: {error}"
            # Keep the lightweight Vosk path as an operational fallback.
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model

            if not self.vosk_model_dir.exists():
                raise RuntimeError(f"Vosk model not found: {self.vosk_model_dir}")

            model = Model(str(self.vosk_model_dir))
            recognizer = KaldiRecognizer(model, 16000)
            audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=12)

            def callback(indata, frames, time_info, status):
                if status:
                    # PortAudio can report recoverable input overflow while
                    # the Vosk loop is handling a completed utterance. Do not
                    # turn that transient callback flag into a fatal-looking
                    # runtime error in the UI.
                    status_text = str(status)
                    if "overflow" not in status_text.lower():
                        self._last_error = status_text
                if self._speaking.is_set() or not self._microphone_enabled:
                    return
                try:
                    audio_queue.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            device = None if self._device_index < 0 else self._device_index
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=4000,
                device=device,
                dtype="int16",
                channels=1,
                latency="high",
                callback=callback,
            ):
                self._phase = "слушаю"
                while not self._stop.is_set():
                    if not self._microphone_enabled:
                        self._phase = "микрофон выключен"
                        time.sleep(0.1)
                        continue
                    self._phase = "слушаю"
                    try:
                        data = audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result() or "{}")
                        text = str(result.get("text") or "").strip().lower()
                        if text:
                            self._handle_transcript(text)
        except Exception as error:
            self._last_error = f"voice runtime: {error}"
            self._phase = "ошибка"
        finally:
            self._enabled = False

    def _run_vad_whisper(self, recognizer, vad) -> None:
        import sounddevice as sd

        audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=32)
        speech: list[bytes] = []
        speaking = False
        silence_blocks = 0
        silence_limit = 8  # 8 * 250 ms = 2 seconds of silence

        def callback(indata, frames, time_info, status):
            if status and "overflow" not in str(status).lower():
                self._last_error = str(status)
            if self._speaking.is_set() or not self._microphone_enabled:
                return
            try:
                audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

        device = None if self._device_index < 0 else self._device_index
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=4000,
            device=device,
            dtype="int16",
            channels=1,
            latency="high",
            callback=callback,
        ):
            self._phase = "слушаю (Silero VAD)"
            while not self._stop.is_set():
                if not self._microphone_enabled:
                    self._phase = "микрофон выключен"
                    time.sleep(0.1)
                    continue
                try:
                    block = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                active = vad.is_speech(block)
                if active:
                    speech.append(block)
                    speaking = True
                    silence_blocks = 0
                    self._phase = "слышу (Silero VAD)"
                elif speaking:
                    speech.append(block)
                    silence_blocks += 1
                    if silence_blocks >= silence_limit:
                        self._phase = "распознаю (faster-whisper)"
                        audio = b"".join(speech)
                        speech.clear()
                        speaking = False
                        silence_blocks = 0
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                            path = Path(handle.name)
                        try:
                            with wave.open(str(path), "wb") as output:
                                output.setnchannels(1)
                                output.setsampwidth(2)
                                output.setframerate(16000)
                                output.writeframes(audio)
                            text = recognizer.transcribe(path)
                            if text:
                                self._handle_transcript(text.lower())
                        finally:
                            path.unlink(missing_ok=True)
                        self._phase = "слушаю (Silero VAD)"

    def _extract_command(self, text: str) -> str | None:
        normalized = " ".join(text.lower().split())
        for wake_word in sorted(self.WAKE_WORDS, key=len, reverse=True):
            if wake_word in normalized:
                command = normalized.replace(wake_word, " ", 1).strip(" ,.!?")
                return command
        if time.monotonic() < self._follow_up_until:
            return normalized
        return None

    def _handle_transcript(self, text: str) -> None:
        command = self._extract_command(text)
        if command is None:
            return
        self._last_transcript = text
        self._phase = "распознал"
        if not command:
            self._phase = "отвечаю WAV"
            self._say_wav("Да сэр.wav")
            self._follow_up_until = time.monotonic() + 10.0
            return
        route = self._response_router.route(command)
        if route.kind == "preset" and route.intent == "hello":
            self._say_wav(self.ACK_FILES["hello"])
            return

        try:
            from computer_control import run_command

            intent = route.intent if route.kind == "command" else None
            self._phase = "проверяю команду"
            if intent == "thanks":
                self._say_wav(self.ACK_FILES["thanks"])
                return
            if intent == "off":
                self._say_wav(self.ACK_FILES["off"])
                self.stop()
                return
            if intent == "sound_off":
                self._phase = "выполняю команду"
                self._say_wav(self.COMMAND_WAVS["sound_off"])
                if not run_command(command):
                    self._last_error = "Не удалось выключить звук"
                return
            if intent:
                self._phase = "выполняю команду"
                handled = bool(run_command(command))
                if handled:
                    self._say_wav(self.COMMAND_WAVS.get(intent, "Да сэр.wav"))
                    if intent == "off":
                        self.stop()
                    return
                self._last_error = f"command_action_missing:{intent}"
                self._say_wav("Я провел симуляции со всеми известными элементами.wav")
                return
        except Exception as error:
            self._last_error = f"command: {error}"
            self._say_wav("Сэр, для реальной попытки полета не просчитаны еще террабайты данных.wav")
            return

        try:
            self._phase = "думаю"
            self._conversation_queue.put_nowait(command)
        except queue.Full:
            self._last_error = "conversation queue is full"
            self._phase = "ошибка"
            self._say_wav("Я провел симуляции со всеми известными элементами.wav")

    def _conversation_loop(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._conversation_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if text is None:
                return
            self._phase = "думаю"
            try:
                self._respond_conversationally(text)
            except Exception as error:
                self._last_error = f"conversation worker: {error}"
                self._phase = "ошибка"

    def _say_wav(self, filename: str, wait_done: bool = True) -> None:
        path = self.voice_dir / filename
        if not path.exists():
            self._last_error = f"WAV response not found: {path.name}"
            return
        try:
            from voice_engine.voice_player import play_voice

            self._last_response = f"wav:{path.name}"
            self._phase = "говорю WAV"
            def play():
                self._speaking.set()
                try:
                    play_voice(str(path))
                finally:
                    self._speaking.clear()
                    if self._enabled:
                        self._phase = "слушаю"

            if wait_done:
                play()
            else:
                threading.Thread(
                    target=play,
                    name="jarvis-wav-ack",
                    daemon=True,
                ).start()
        except Exception as error:
            self._last_error = f"wav: {error}"

    def _respond_conversationally(self, text: str) -> None:
        try:
            from services.llm_service import LocalLLMService

            # Start the acknowledgement immediately, but overlap its playback
            # with LLM generation so the user is not forced to wait for a WAV
            # before Ollama even receives the question.
            self._say_wav("Всегда к вашим услугам сэр.wav", wait_done=False)
            self._phase = "думаю"
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты Jarvis. Отвечай по-русски кратко и естественно, "
                        "обычно 1-3 предложениями. Не добавляй планы проектов, "
                        "markdown, служебные блоки и длинные списки, если их не просили. "
                        "Если смысл запроса невозможно понять, ответь ровно "
                        "__JARVIS_NOT_UNDERSTOOD__."
                    ),
                },
                *self._conversation_history[-8:],
                {"role": "user", "content": text},
            ]
            response = asyncio.run(self._stream_response(LocalLLMService(), messages))
            response = " ".join(str(response or "").split()).strip()
            # Voice replies must stay short. Long Ollama completions make CPU
            # TTS dominate the interaction and are poor spoken responses.
            if len(response) > 280:
                response = response[:280].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
            if not response or "__JARVIS_NOT_UNDERSTOOD__" in response:
                self._last_error = "conversation returned an empty response"
                self._say_wav("Создать визуальный образ по новым спецификациям.wav")
                return
            self._conversation_history.extend([
                {"role": "user", "content": text},
                {"role": "assistant", "content": response},
            ])
            self._last_response = response
            self._tts_available = True
            if self._tts_queue is None:
                from voice_engine.tts import speak

                self._tts_queue = TTSQueue(speak)
            self._phase = "говорю AI по предложениям"
            self._tts_queue.wait_idle(timeout=90.0)
            if self._enabled:
                self._phase = "слушаю"
        except Exception as error:
            self._tts_available = False
            self._last_error = f"conversation TTS: {error}"
            self._phase = "ошибка"
            self._say_wav("Сэр, для реальной попытки полета не просчитаны еще террабайты данных.wav")

    async def _stream_response(self, service, messages: list[dict[str, str]]) -> str:
        """Stream Ollama text and enqueue each completed sentence immediately."""
        chunks: list[str] = []
        pending = ""
        async for chunk in service.chat_stream(messages):
            pending += str(chunk or "")
            chunks.append(str(chunk or ""))
            while True:
                boundary = next((index for index, char in enumerate(pending) if char in ".!?\n"), -1)
                if boundary < 0:
                    break
                sentence, pending = pending[: boundary + 1], pending[boundary + 1 :]
                if self._tts_queue is None:
                    from voice_engine.tts import speak

                    self._tts_queue = TTSQueue(speak)
                self._tts_queue.put(sentence)
        if pending.strip():
            if self._tts_queue is None:
                from voice_engine.tts import speak

                self._tts_queue = TTSQueue(speak)
            self._tts_queue.put(pending)
        return "".join(chunks)
