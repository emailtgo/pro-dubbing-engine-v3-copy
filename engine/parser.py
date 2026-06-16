import re
import datetime
from typing import List
from engine.models import DubbingSegment

class Parser:
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert HH:MM:SS,ms or MM:SS to seconds"""
        time_str = time_str.replace(",", ".").strip("[] ")
        parts = time_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(time_str)

    def _seconds_to_time(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS,ms"""
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds_int = divmod(remainder, 60)
        milliseconds = int((seconds - total_seconds) * 1000)
        return f"{hours:02}:{minutes:02}:{seconds_int:02},{milliseconds:03}"

    def parse_srt(self, srt_content: str, output_language: str) -> List[DubbingSegment]:
        """Parse SRT content into DubbingSegments"""
        segments = []
        # Support various SRT formats and line endings
        pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2}[,. ]\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}[,. ]\d{3})\s+(.*?)(?=\n\n|\r\n\r\n|\n\d+\n|\r\n\d+\r\n|$)'
        matches = re.finditer(pattern, srt_content, re.DOTALL)
        
        for i, match in enumerate(matches):
            start_s = self._time_to_seconds(match.group(2))
            end_s = self._time_to_seconds(match.group(3))
            text = match.group(4).replace('\n', ' ').replace('\r', '').strip()
            
            segments.append(DubbingSegment(
                start=start_s,
                end=end_s,
                lang=output_language,
                text=text,
                segment_id=i
            ))
        return segments

    def group_segments_into_sentences(self, segments: List[DubbingSegment]) -> List[DubbingSegment]:
        """Group segments based on sentence-ending punctuation. Returns segments with sentence_id assigned."""
        sentences = []
        current_batch = []
        sentence_id = 1
        
        # Sentence ending markers for various languages
        end_markers = r'[.!?။၊၊]' # Includes Myanmar markers
        
        for seg in segments:
            current_batch.append(seg)
            # Check if the text ends with a sentence marker
            if re.search(end_markers + r'\s*$', seg.text) or seg == segments[-1]:
                # Create a dummy DubbingSentence to hold grouped segments for now
                # The actual DubbingSentence object will be created in the engine
                for s in current_batch:
                    s.sentence_id = sentence_id
                sentences.extend(current_batch)
                current_batch = []
                sentence_id += 1
                
        return sentences # Returns segments with sentence_id assigned

    def reconstruct_srt_with_translation(self, original_segments: List[DubbingSegment], translated_text: str) -> str:
        """Reconstruct SRT using original timestamps and translated text lines."""
        translated_lines = [l.strip() for l in translated_text.strip().split('\n') if l.strip()]
        
        srt_out = []
        for i, seg in enumerate(original_segments):
            text = translated_lines[i] if i < len(translated_lines) else seg.text
            start_t = self._seconds_to_time(seg.start)
            end_t = self._seconds_to_time(seg.end)
            srt_block = f"{i+1}\n{start_t} --> {end_t}\n{text}\n"
            srt_out.append(srt_block)
        
        return "\n".join(srt_out)

    def generate_srt_content(self, segments: List[DubbingSegment]) -> str:
        """Generate final SRT content using adjusted text."""
        srt_out = []
        for i, seg in enumerate(segments):
            start_t = self._seconds_to_time(seg.start)
            end_t = self._seconds_to_time(seg.end)
            # BUG FIX: Use seg.adjusted_text instead of seg.text
            srt_out.append(f"{i+1}\n{start_t} --> {end_t}\n{seg.adjusted_text}\n")
        return "\n".join(srt_out)
