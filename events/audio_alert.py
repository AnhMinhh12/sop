import sounddevice as sd
import soundfile as sf
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

class AudioAlert:
    """
    Plays an alert sound when a violation occurs.
    Thread-safe and includes a cooldown mechanism.
    """
    def __init__(self, sound_file: str, volume: float = 0.8, cooldown_sec: int = 10):
        self.sound_file = sound_file
        self.volume = volume
        self.cooldown_sec = cooldown_sec
        
        self.last_alert_time = 0
        self.lock = threading.Lock()
        
        # Check for available audio output devices
        self.device_available = False
        try:
            devices = sd.query_devices()
            if any(d['max_output_channels'] > 0 for d in devices):
                self.device_available = True
            else:
                logger.warning("AudioAlert: No audio output device found. Audio alerts will be disabled.")
        except Exception as e:
            logger.warning(f"AudioAlert: Could not query audio devices: {e}. Audio alerts will be disabled.")

        # Load sound data once
        try:
            if self.device_available:
                self.data, self.fs = sf.read(sound_file)
                # Apply volume
                self.data = self.data * volume
                logger.info(f"AudioAlert: Loaded alert sound from {sound_file}")
            else:
                self.data = None
        except Exception as e:
            logger.error(f"AudioAlert: Failed to load sound file: {e}")
            self.data = None

    def trigger(self):
        """
        Triggers the alert sound if not in cooldown.
        Runs in a separate thread to avoid blocking.
        """
        if self.data is None:
            return

        with self.lock:
            current_time = time.time()
            if current_time - self.last_alert_time < self.cooldown_sec:
                return
            
            self.last_alert_time = current_time
            
        # Phát âm thanh trong thread riêng
        threading.Thread(target=self._play, daemon=True).start()

    def _play(self):
        try:
            # Chỉ phát tối đa 2 giây âm thanh đầu tiên
            duration_to_play = 2.0
            samples_to_play = int(duration_to_play * self.fs)
            
            if len(self.data) > samples_to_play:
                play_data = self.data[:samples_to_play]
            else:
                play_data = self.data

            sd.play(play_data, self.fs)
            sd.wait() # Chờ phát xong (tối đa 2s)
            logger.info("AudioAlert: Alert sound played (2s limit).")
        except Exception as e:
            logger.error(f"AudioAlert: Error playing sound: {e}")
