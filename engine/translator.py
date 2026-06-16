import re
import asyncio
import time
from typing import List, Dict, Union
from google import genai
from google.genai import types

class Translator:
    def __init__(self, api_keys: List[str] = None, max_rpm: int = 9):
        self.api_keys = api_keys if api_keys else []
        self.max_rpm = max_rpm
        self.current_key_index = 0
        self.api_lock = asyncio.Lock() # Lock for thread-safe/async-safe rotation
        self.key_usage = {key: [] for key in self.api_keys}
        self.gemini_model = 'gemini-3.5-flash'

    async def _get_next_client(self):
        """Rotate through API keys and return a configured GenAI client with rate limit awareness.
        BUG FIX: Ensure lock is released and prevent potential deadlock.
        """
        if not self.api_keys:
            return None
        
        while True:
            key = None
            async with self.api_lock:
                attempts = 0
                while attempts < len(self.api_keys):
                    current_key_candidate = self.api_keys[self.current_key_index]
                    self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                    attempts += 1
                    
                    now = time.time()
                    # Clean up old timestamps (older than 60s)
                    self.key_usage[current_key_candidate] = [t for t in self.key_usage[current_key_candidate] if now - t < 60]
                    
                    if len(self.key_usage[current_key_candidate]) < self.max_rpm:
                        key = current_key_candidate
                        self.key_usage[key].append(now)
                        break # Found an available key, break from inner loop
            
            if key:
                return genai.Client(api_key=key)
            
            # All keys are at limit, wait a bit and loop again after releasing the lock
            print("All API keys are at rate limit. Waiting 5 seconds...")
            await asyncio.sleep(5)

    async def translate_batch_parallel(self, text: str, target_lang: str, num_workers: int = 5) -> str:
        """Translate text in parallel by splitting it into chunks, trying to split at sentence ends."""
        input_lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        if not input_lines:
            return ""
        
        total_lines = len(input_lines)
        if num_workers <= 1 or total_lines <= 10:
            return await self._translate_chunk(input_lines, target_lang, 0, as_string=True)
            
        # Sentence-Aware Chunking:
        ideal_chunk_size = total_lines // num_workers
        chunks = []
        current_chunk = []
        
        for i, line in enumerate(input_lines):
            current_chunk.append(line)
            is_sentence_end = any(line.endswith(p) for p in ['.', '?', '!'])
            is_last_line = (i == total_lines - 1)
            
            if (len(current_chunk) >= ideal_chunk_size and is_sentence_end) or \
               (len(current_chunk) >= ideal_chunk_size * 1.5) or \
               is_last_line:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
        
        if current_chunk:
            if chunks:
                chunks[-1].extend(current_chunk)
            else:
                chunks.append(current_chunk)

        tasks = []
        current_start_index = 0
        for chunk in chunks:
            tasks.append(self._translate_chunk(chunk, target_lang, current_start_index))
            current_start_index += len(chunk)
        
        results = await asyncio.gather(*tasks)
        
        all_translated_lines = []
        for i, res in enumerate(results):
            if isinstance(res, list):
                all_translated_lines.extend(res)
            else:
                # BUG FIX: Use len(chunks[i]) instead of undefined chunk_size
                all_translated_lines.extend([f"[Chunk Error: {res}]"] * len(chunks[i]))
        
        return "\n".join(all_translated_lines[:len(input_lines)])

    async def _translate_chunk(self, lines: List[str], target_lang: str, start_index: int, as_string: bool = False) -> Union[List[str], str]:
        """Helper to translate a specific chunk of lines."""
        max_retries = 3
        retry_delay = 2
        
        numbered_input = "\n".join([f"L{start_index + i + 1}: {line}" for i, line in enumerate(lines)])
        
        word_count = sum(len(l.split()) for l in lines)
        dynamic_tokens = max(5000, min(32768, word_count * 15))
        
        config = types.GenerateContentConfig(
            max_output_tokens=dynamic_tokens,
            temperature=0.7
        )
        
        prompt = f"""You are a professional translator. Translate the following numbered lines into {target_lang}.

### STRICT RULES:
1. Your response MUST start directly with 'L{start_index + 1}:' followed by the translation.
2. DO NOT include any introductory text, thinking process, explanations, notes, or concluding remarks.
3. Maintain the exact line markers (L{start_index + 1}:, L{start_index + 2}:, etc.) for every single line.
4. Do not merge lines. Every input line must have exactly one corresponding output line.
5. Translate all {len(lines)} lines without skipping any.
"""
        
        for attempt in range(max_retries):
            client = await self._get_next_client()
            if not client:
                return [f"[Error: No API keys]"] * len(lines)

            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.gemini_model,
                    contents=f"{prompt}\n\n{numbered_input}",
                    config=config
                )
                translated_raw = response.text.strip()
                
                chunk_output = [f"[Line {start_index + i + 1} Translation Missing]" for i in range(len(lines))]
                parts = re.split(r"(L\d+[:\-\.\s]+)", translated_raw)
                
                for i in range(1, len(parts), 2):
                    marker_part = parts[i]
                    text_part = parts[i+1]
                    
                    try:
                        line_match = re.search(r"\d+", marker_part)
                        if line_match:
                            line_num = int(line_match.group())
                            if start_index + 1 <= line_num <= start_index + len(lines):
                                clean_text = text_part.strip().split('\n')[0].strip()
                                chunk_output[line_num - start_index - 1] = clean_text
                    except:
                        continue
                
                return "\n".join(chunk_output) if as_string else chunk_output

            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                err_res = [f"[Error: {error_msg}]"] * len(lines)
                return "\n".join(err_res) if as_string else err_res
        
        err_res = [f"[Error: Max retries reached]"] * len(lines)
        return "\n".join(err_res) if as_string else err_res

    async def _rewrite_text_with_ai(self, original_text: str, target_duration: float, current_tts_duration: float, lang: str) -> str:
        """Use Gemini AI to rewrite text to better fit target duration with Retry logic."""
        max_retries = 50 # User requested 50 retries
        retry_delay = 2

        duration_diff = current_tts_duration - target_duration
        if duration_diff > 0: # TTS is too long, need to shorten text
            prompt = f"""
            The following {lang} text was spoken in {current_tts_duration:.2f} seconds, but it needs to fit into {target_duration:.2f} seconds. 
            Please rewrite the text to be shorter, while retaining its original meaning as much as possible. 
            Do not add any introductory or concluding phrases. Just provide the rewritten text.
            Original text: {original_text}
            Rewritten text:
            """
        else: # TTS is too short, need to lengthen text
            prompt = f"""
            The following {lang} text was spoken in {current_tts_duration:.2f} seconds, but it needs to be {target_duration:.2f} seconds long. 
            Please rewrite the text to be slightly longer, adding natural pauses or descriptive words, while retaining its original meaning as much as possible. 
            Do not add any introductory or concluding phrases. Just provide the rewritten text.
            Original text: {original_text}
            Rewritten text:
            """
        config = types.GenerateContentConfig(
            max_output_tokens=5000, # Fixed size for short rewrites
            temperature=0.7
        )
        for attempt in range(max_retries):
            client = await self._get_next_client()
            if not client:
                return original_text

            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.gemini_model,
                    contents=prompt,
                    config=config
                )
                rewritten_text = response.text.strip()
                if rewritten_text.lower().startswith("rewritten text:"):
                    rewritten_text = rewritten_text[len("rewritten text:"):].strip()
                return rewritten_text
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        print(f"Server 503 error in rewrite. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                print(f"AI rewrite failed: {error_msg}")
                return original_text
        return original_text
