import os
from typing import List
from pydub import AudioSegment
import io
from engine.models import DubbingSegment

class AudioProcessor:
    def __init__(self, bitrate: str = "192k"):
        self.bitrate = bitrate

    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of an audio file using pydub."""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # duration in seconds
        except Exception as e:
            print(f"Error getting audio duration for {audio_path}: {e}")
            return 0.0

    def adjust_audio_speed(self, audio_path: str, target_duration: float, output_path: str) -> bool:
        """Adjust audio speed to match target duration."""
        try:
            audio = AudioSegment.from_file(audio_path)
            current_duration = len(audio) / 1000.0
            if current_duration == 0:
                return False
            
            speed_factor = current_duration / target_duration
            
            # Limit speed adjustment to reasonable range (0.5x to 2.0x)
            speed_factor = max(0.5, min(2.0, speed_factor))
            
            # Apply speed adjustment
            adjusted_audio = audio.speedup(playback_speed=speed_factor)
            
            # Normalize volume
            adjusted_audio = adjusted_audio.normalize()

            adjusted_audio.export(output_path, format="mp3", bitrate=self.bitrate)
            return True
        except Exception as e:
            print(f"Error adjusting audio speed for {audio_path}: {e}")
            return False

    def merge_audio_files(self, segments: List[DubbingSegment], output_path: str) -> bool:
        """Merge individual segment audios into one file with precise timing."""
        try:
            if not segments:
                return False
            
            total_duration_ms = int(segments[-1].end * 1000)
            combined = AudioSegment.silent(duration=total_duration_ms)
            
            processed_sentences = set()
            
            for seg in segments:
                # BUG FIX: Ensure sentence_id is not None before checking
                if seg.sentence_id is None or seg.sentence_id in processed_sentences:
                    continue
                
                if seg.tts_audio_path and os.path.exists(seg.tts_audio_path):
                    audio = AudioSegment.from_file(seg.tts_audio_path)
                    sentence_start_ms = int(seg.start * 1000)
                    combined = combined.overlay(audio, position=sentence_start_ms)
                    processed_sentences.add(seg.sentence_id)
            
            combined.export(output_path, format="mp3", bitrate=self.bitrate)
            return True
        except Exception as e:
            print(f"Error merging audio: {e}")
            return False
