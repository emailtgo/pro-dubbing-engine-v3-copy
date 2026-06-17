import asyncio
import os
import edge_tts
from typing import List
from engine.models import DubbingSentence, DubbingChunk
from engine.translator import Translator
from engine.audio_processor import AudioProcessor

class TTSHandler:
    def __init__(self, output_language: str = "my", voice_gender: str = "Male", 
                 tolerance: float = 0.3, max_ai_retries: int = 50, 
                 translator: Translator = None, audio_processor: AudioProcessor = None):
        self.tolerance = tolerance
        self.output_language = output_language.lower()
        self.voice_gender = voice_gender
        self.max_ai_retries = max_ai_retries
        self.translator = translator
        self.audio_processor = audio_processor
        self.voice_map = {
            "my": {"Male": "my-MM-ThihaNeural", "Female": "my-MM-NilarNeural"},
            "en": {"Male": "en-US-GuyNeural", "Female": "en-US-AvaNeural"},
            "ja": {"Male": "ja-JP-KeitaNeural", "Female": "ja-JP-NanamiNeural"},
            "ko": {"Male": "ko-KR-InJoonNeural", "Female": "ko-KR-SunHiNeural"},
            "th": {"Male": "th-TH-NiwatNeural", "Female": "th-TH-PremwadeeNeural"},
            "vi": {"Male": "vi-VN-NamMinhNeural", "Female": "vi-VN-HoaiMyNeural"}
        }

    async def process_chunk(self, chunk: DubbingChunk, output_dir: str, status_callback=None):
        """Process all sentences in a chunk sequentially to maintain flow, but chunks run in parallel."""
        chunk.status = "processing"
        total = len(chunk.sentences)
        for i, sentence in enumerate(chunk.sentences):
            await self.generate_tts_with_retry(sentence, output_dir, status_callback)
            chunk.progress = (i + 1) / total
        chunk.status = "completed"

    async def generate_tts_with_retry(self, sentence: DubbingSentence, output_dir: str, status_callback=None):
        target_duration = sentence.duration
        sentence.retries = 0
        lang_voices = self.voice_map.get(self.output_language, self.voice_map["my"])
        voice = lang_voices.get(self.voice_gender, lang_voices["Male"])

        while sentence.retries < self.max_ai_retries:
            temp_path = os.path.join(output_dir, f"temp_{sentence.sentence_id}_{sentence.retries}.mp3")
            
            # 1. Generate TTS
            communicate = edge_tts.Communicate(sentence.adjusted_text, voice)
            await communicate.save(temp_path)
            
            # 2. Check Duration
            current_duration = self.audio_processor.get_audio_duration(temp_path)
            sentence.tts_duration = current_duration
            
            if status_callback:
                status_callback(sentence.sentence_id, f"Try {sentence.retries}: {current_duration:.2f}s (Target: {target_duration:.2f}s)")

            # 3. Decision
            if abs(current_duration - target_duration) <= self.tolerance:
                final_path = os.path.join(output_dir, f"sent_{sentence.sentence_id}.mp3")
                # Final speed adjustment for perfect match
                self.audio_processor.adjust_audio_speed(temp_path, target_duration, final_path)
                sentence.tts_audio_path = final_path
                sentence.status = "completed"
                return True
            
            # 4. Rewrite if not matched
            if self.translator:
                sentence.adjusted_text = await self.translator.rewrite_to_fit_duration(
                    sentence.text, sentence.adjusted_text, target_duration, current_duration, self.output_language
                )
            
            sentence.retries += 1
        
        # Fallback: Just speed adjust the last attempt if max retries reached
        final_path = os.path.join(output_dir, f"sent_{sentence.sentence_id}.mp3")
        self.audio_processor.adjust_audio_speed(temp_path, target_duration, final_path)
        sentence.tts_audio_path = final_path
        sentence.status = "completed"
        return True
