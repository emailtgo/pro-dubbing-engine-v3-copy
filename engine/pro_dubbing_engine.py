import asyncio
import os
import nest_asyncio
import re
from typing import List, Dict
from engine.models import DubbingSegment, DubbingSentence, DubbingChunk
from engine.parser import Parser
from engine.translator import Translator
from engine.tts_handler import TTSHandler
from engine.audio_processor import AudioProcessor

class ProDubbingEngine:
    def __init__(self, api_keys: List[str], output_language: str = "my", voice_gender: str = "Male",
                 tolerance: float = 0.3, max_ai_retries: int = 50, max_rpm: int = 9, bitrate: str = "192k"):
        
        nest_asyncio.apply()
        self.parser = Parser()
        self.translator = Translator(api_keys=api_keys, max_rpm=max_rpm)
        self.audio_processor = AudioProcessor(bitrate=bitrate)
        self.tts_handler = TTSHandler(output_language=output_language, voice_gender=voice_gender,
                                      tolerance=tolerance, max_ai_retries=max_ai_retries,
                                      translator=self.translator, audio_processor=self.audio_processor)
        
        self.output_language = output_language
        self.voice_gender = voice_gender

    async def prepare_srt(self, input_text: str) -> str:
        """Step 1: Convert input (Text or SRT) into a precise translated SRT."""
        return await self.translator.translate_text_to_srt(input_text, self.output_language)

    async def create_chunks(self, srt_content: str, num_chunks: int) -> List[DubbingChunk]:
        """Parse SRT and group segments into sentences based on punctuation."""
        segments = self.parser.parse_srt(srt_content, self.output_language)
        
        # Sentence Grouping Logic
        sentences = []
        current_segments = []
        end_markers = r'[.!?။၊၊]'
        
        for seg in segments:
            current_segments.append(seg)
            if re.search(end_markers + r'\s*$', seg.text) or seg == segments[-1]:
                sentences.append(DubbingSentence(current_segments, len(sentences) + 1))
                current_segments = []
        
        # Divide sentences into chunks for parallel processing
        chunk_size = max(1, len(sentences) // num_chunks)
        chunks = []
        for i in range(0, len(sentences), chunk_size):
            chunk_sentences = sentences[i:i + chunk_size]
            chunks.append(DubbingChunk(chunk_sentences, len(chunks) + 1))
        
        return chunks

    async def process_parallel(self, chunks: List[DubbingChunk], status_callback=None):
        """Step 2: Run all chunks in parallel."""
        output_dir = "./temp_audio"
        os.makedirs(output_dir, exist_ok=True)
        
        tasks = [self.tts_handler.process_chunk(chunk, output_dir, status_callback) for chunk in chunks]
        await asyncio.gather(*tasks)
        return chunks

    async def finalize(self, chunks: List[DubbingChunk]) -> Dict:
        """Step 3: Merge all and generate final outputs."""
        all_sentences = []
        for chunk in chunks:
            all_sentences.extend(chunk.sentences)
        
        # Reconstruct segments from sentences for SRT generation
        final_segments = []
        for sentence in all_sentences:
            # Distribute the adjusted sentence text back to segments if needed, 
            # but for SRT we might just want to keep them as is or use the new text.
            # User wants translated srt separately.
            for seg in sentence.segments:
                # Simple distribution: put full sentence text in first segment, others empty 
                # or keep original. For now, let's keep them mapped.
                final_segments.append(seg)
        
        final_audio_path = os.path.join("./temp_audio", "final_dubbed_audio.mp3")
        # Use sentences for merging to ensure correct timing placement
        self.audio_processor.merge_audio_files_from_sentences(all_sentences, final_audio_path)
        
        final_srt_content = self.parser.generate_srt(final_segments)
        
        return {
            "final_audio_path": final_audio_path,
            "final_srt_content": final_srt_content
        }

    def run_sync(self, coro):
        return asyncio.run(coro)
