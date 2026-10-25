import logging
import sys

from gerald.audio.mic import Microphone
from gerald.audio.player import AudioPlayer


def test_audio_player_is_a_noop_when_sounddevice_cannot_import(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    player = AudioPlayer()

    with caplog.at_level(logging.WARNING):
        player.enqueue(b"\0\0")
        player.enqueue(b"\0\0")

    assert player.available is False
    assert player._stream is None
    assert player._chunks.empty()
    assert sum("Audio output unavailable" in record.message for record in caplog.records) == 1


def test_microphone_is_a_noop_when_sounddevice_cannot_import(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    microphone = Microphone(lambda _audio, _level: None)

    with caplog.at_level(logging.WARNING):
        microphone.start()
        microphone.start()

    assert microphone.available is False
    assert microphone._stream is None
    assert sum("Microphone unavailable" in record.message for record in caplog.records) == 1
