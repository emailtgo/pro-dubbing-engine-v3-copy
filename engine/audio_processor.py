import os
from typing import List
from pydub import AudioSegment
from engine.models import DubbingSentence

class AudioProcessor:
    def __init__(self, bitrate: str = "192k"):
        self.bitrate = bitrate

    def get_audio_duration(self, file_path: str) -> float:
        if not os.path.exists(file_path):
            return 0.0
        try:
            audio = AudioSegment.from_file(file_path)
            return len(audio) / 1000.0
        except Exception:
            return 0.0

    def adjust_audio_speed(self, input_path: str, target_duration: float, output_path: str):
        try:
            audio = AudioSegment.from_file(input_path)
            current_duration = len(audio) / 1000.0
            if current_duration == 0: return
            
            speed_factor = current_duration / target_duration
            speed_factor = max(0.5, min(2.0, speed_factor))
            
            if speed_factor != 1.0:
                # Use speedup for faster, and simple frame rate change for slower (pydub speedup only supports > 1.0)
                if speed_factor > 1.0:
                    audio = audio.speedup(playback_speed=speed_factor)
                else:
                    # Slow down by changing frame rate
                    new_sample_rate = int(audio.frame_rate * speed_factor)
                    audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
                    audio = audio.set_frame_rate(44100)
            
            # Ensure exact duration by padding or cropping
            target_ms = int(target_duration * 1000)
            if len(audio) < target_ms:
                audio = audio + AudioSegment.silent(duration=target_ms - len(audio))
            else:
                audio = audio[:target_ms]
                
            audio.export(output_path, format="mp3", bitrate=self.bitrate)
        except Exception as e:
            print(f"Error adjusting speed: {e}")

    def merge_audio_files_from_sentences(self, sentences: List[DubbingSentence], output_path: str):
        if not sentences:
            return
        
        sentences.sort(key=lambda x: x.start)
        total_duration_ms = int(sentences[-1].end * 1000)
        combined = AudioSegment.silent(duration=total_duration_ms)
        
        for sentence in sentences:
            if sentence.tts_audio_path and os.path.exists(sentence.tts_audio_path):
                clip = AudioSegment.from_file(sentence.tts_audio_path)
                start_ms = int(sentence.start * 1000)
                combined = combined.overlay(clip, position=start_ms)
        
        # Normalize volume (Leveling)
        combined = combined.normalize()
        combined.export(output_path, format="mp3", bitrate=self.bitrate)
