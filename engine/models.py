from typing import List, Optional

class DubbingSegment:
    def __init__(self, start: float, end: float, text: str, segment_id: int, lang: str = "my"):
        self.start = start
        self.end = end
        self.duration = end - start
        self.text = text
        self.segment_id = segment_id
        self.lang = lang
        self.adjusted_text = text
        self.sentence_id: Optional[int] = None

class DubbingSentence:
    def __init__(self, segments: List[DubbingSegment], sentence_id: int):
        self.segments = segments
        self.sentence_id = sentence_id
        self.start = segments[0].start
        self.end = segments[-1].end
        self.duration = self.end - self.start
        self.text = " ".join([s.text for s in segments])
        self.adjusted_text = self.text
        self.tts_audio_path: Optional[str] = None
        self.tts_duration: float = 0.0
        self.retries: int = 0
        self.status: str = "pending" # pending, processing, completed, failed

class DubbingChunk:
    def __init__(self, sentences: List[DubbingSentence], chunk_id: int):
        self.sentences = sentences
        self.chunk_id = chunk_id
        self.status = "pending"
        self.progress = 0.0
