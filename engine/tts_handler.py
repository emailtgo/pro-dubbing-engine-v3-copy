import asyncio
import os
import edge_tts
from typing import List, Dict
from engine.models import DubbingSentence
from engine.translator import Translator
from engine.audio_processor import AudioProcessor

class TTSHandler:
    def __init__(self, output_language: str = "my", voice_gender: str = "Male", tolerance: float = 0.3, max_ai_retries: int = 50, translator: Translator = None, audio_processor: AudioProcessor = None):
        self.tolerance = tolerance
        self.output_language = output_language.lower()
        self.voice_gender = voice_gender
        self.max_ai_retries = max_ai_retries
        self.translator = translator
        self.audio_processor = audio_processor
        self._initialize_voice_map()

    def _initialize_voice_map(self):
        self.voice_map = {
            "my": {"Male": "my-MM-ThihaNeural", "Female": "my-MM-NilarNeural"},
            "en": {"Male": "en-US-GuyNeural", "Female": "en-US-AvaNeural"},
            "ja": {"Male": "ja-JP-KeitaNeural", "Female": "ja-JP-NanamiNeural"},
            "ko": {"Male": "ko-KR-InJoonNeural", "Female": "ko-KR-SunHiNeural"},
            "th": {"Male": "th-TH-NiwatNeural", "Female": "th-TH-PremwadeeNeural"},
            "vi": {"Male": "vi-VN-NamMinhNeural", "Female": "vi-VN-HoaiMyNeural"}
        }

    async def generate_tts_for_sentence(self, sentence: DubbingSentence, output_dir: str, status_callback=None) -> bool:
        """Generate TTS for a full sentence with iterative text rewriting and speed adjustment."""
        target_duration = sentence.duration
        sentence.retries = 0

        while True:
            try:
                if status_callback:
                    status_callback(sentence.sentence_id, f"Processing (Attempt {sentence.retries + 1})")
                
                lang_voices = self.voice_map.get(self.output_language, self.voice_map["my"])
                voice = lang_voices.get(self.voice_gender, lang_voices["Male"])
                
                temp_output_path = os.path.join(output_dir, f"temp_sent_{sentence.sentence_id}.mp3")
                try:
                    communicate = edge_tts.Communicate(sentence.adjusted_text, voice)
                    await communicate.save(temp_output_path)
                except Exception as e:
                    print(f"Edge-TTS failed: {e}")
                    sentence.retries += 1
                    if sentence.retries >= self.max_ai_retries:
                        return False
                    await asyncio.sleep(1)
                    continue
                
                tts_duration = self.audio_processor.get_audio_duration(temp_output_path)
                sentence.tts_duration = tts_duration

                if tts_duration > 0 and (abs(tts_duration - target_duration) <= self.tolerance or sentence.retries >= self.max_ai_retries):
                    final_output_path = os.path.join(output_dir, f"sent_{sentence.sentence_id}.mp3")
                    
                    # Final speed adjustment if still out of tolerance
                    if abs(tts_duration - target_duration) > self.tolerance:
                        self.audio_processor.adjust_audio_speed(temp_output_path, target_duration, final_output_path)
                    else:
                        os.rename(temp_output_path, final_output_path)
                    
                    sentence.tts_audio_path = final_output_path
                    sentence.status = "completed"
                    return True
                
                # If not within tolerance, rewrite and try again
                if self.translator:
                    sentence.adjusted_text = await self.translator._rewrite_text_with_ai(
                        sentence.text, target_duration, tts_duration, self.output_language
                    )
                sentence.retries += 1
                
            except Exception as e:
                print(f"Sentence processing error: {e}")
                return False
