import os
import random
import threading
import sounddevice as sd
import soundfile as sf


# ------------------------------------------------
# путь к папке sound
# ------------------------------------------------

BASE_DIR = os.path.dirname(__file__)
VOICE_DIR = os.path.join(BASE_DIR, "sound")
VOICE_DIR = os.path.abspath(VOICE_DIR)

print("VOICE PLAYER DIR:", VOICE_DIR)


# ------------------------------------------------
# список wav
# ------------------------------------------------

def get_voice_files():

    if not os.path.exists(VOICE_DIR):
        print("Папка sound не найдена:", VOICE_DIR)
        return []

    return [
        f for f in os.listdir(VOICE_DIR)
        if f.lower().endswith(".wav")
    ]


# ------------------------------------------------
# воспроизведение
# ------------------------------------------------

def play_voice(file):

    try:

        # если передан полный путь
        if os.path.isabs(file):
            path = file
        else:
            path = os.path.join(VOICE_DIR, file)

        path = os.path.abspath(path)

        print("play_voice:", path)

        if not os.path.exists(path):
            print("Файл не найден:", path)
            return

        # читаем wav
        data, samplerate = sf.read(path, dtype="float32")

        # если файл стерео → делаем mono
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # воспроизводим
        sd.play(data, samplerate)

        # ждём окончания, но не позволяем драйверу навсегда заблокировать
        # голосовой обработчик
        waiter = threading.Thread(target=sd.wait, name="jarvis-wav-wait", daemon=True)
        waiter.start()
        playback_timeout = max(5.0, min(30.0, len(data) / float(samplerate) + 5.0))
        waiter.join(timeout=playback_timeout)
        if waiter.is_alive():
            sd.stop()

    except Exception as e:

        print("Ошибка воспроизведения:", e)


# ------------------------------------------------
# случайная фраза
# ------------------------------------------------

def random_voice():

    voices = get_voice_files()

    if not voices:
        print("Нет голосовых файлов")
        return

    voice = random.choice(voices)

    play_voice(voice)
