import re
import datetime
from typing import List
from engine.models import DubbingSegment

class Parser:
    def _time_to_seconds(self, time_str: str) -> float:
        time_str = time_str.replace(",", ".").strip("[] ")
        parts = time_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(time_str)

    def _seconds_to_time(self, seconds: float) -> str:
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds_int = divmod(remainder, 60)
        milliseconds = int((seconds - total_seconds) * 1000)
        return f"{hours:02}:{minutes:02}:{seconds_int:02},{milliseconds:03}"

    def parse_srt(self, srt_content: str, lang: str = "my") -> List[DubbingSegment]:
        segments = []
        pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2}[,. ]\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}[,. ]\d{3})\s+(.*?)(?=\n\n|\r\n\r\n|\n\d+\n|\r\n\d+\r\n|$)'
        matches = re.finditer(pattern, srt_content, re.DOTALL)
        
        for i, match in enumerate(matches):
            start_s = self._time_to_seconds(match.group(2))
            end_s = self._time_to_seconds(match.group(3))
            text = match.group(4).replace('\n', ' ').strip()
            segments.append(DubbingSegment(start_s, end_s, text, i, lang))
        return segments

    def generate_srt(self, segments: List[DubbingSegment]) -> str:
        srt_out = []
        for i, seg in enumerate(segments):
            start_t = self._seconds_to_time(seg.start)
            end_t = self._seconds_to_time(seg.end)
            srt_out.append(f"{i+1}\n{start_t} --> {end_t}\n{seg.adjusted_text}\n")
        return "\n".join(srt_out)
