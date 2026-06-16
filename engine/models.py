from typing import List
import datetime

class DubbingSegment:
    def __init__(self, start: float, end: float, lang: str, text: str, segment_id: int):
        self.start = start
        self.end = end
        self.duration = end - start
        self.lang = lang
        self.text = text
        self.segment_id = segment_id
        self.tts_audio_path = None
        self.tts_duration = None
        self.adjusted_text = text
        self.adjusted_speed = 1.0
        self.status = "pending"
        self.original_tts_duration = None
        self.final_audio_path = None
        self.retries = 0
        self.sentence_id = None # To group segments into sentences

class DubbingSentence:
    def __init__(self, segments: List[DubbingSegment], sentence_id: int):
        self.segments = segments
        self.sentence_id = sentence_id
        self.start = segments[0].start
        self.end = segments[-1].end
        self.duration = self.end - self.start
        self.text = " ".join([s.text for s in segments])
        self.adjusted_text = self.text
        self.tts_audio_path = None
        self.tts_duration = None
        self.retries = 0
        self.status = "pending"
