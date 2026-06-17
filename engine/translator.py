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
        self.api_lock = asyncio.Lock()
        self.key_usage = {key: [] for key in self.api_keys}
        self.gemini_model = 'gemini-2.0-flash' # Using a stable flash model

    async def _get_next_client(self):
        if not self.api_keys:
            return None
        
        while True:
            key = None
            async with self.api_lock:
                now = time.time()
                for _ in range(len(self.api_keys)):
                    candidate = self.api_keys[self.current_key_index]
                    self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                    
                    self.key_usage[candidate] = [t for t in self.key_usage[candidate] if now - t < 60]
                    if len(self.key_usage[candidate]) < self.max_rpm:
                        key = candidate
                        self.key_usage[key].append(now)
                        break
            
            if key:
                return genai.Client(api_key=key)
            await asyncio.sleep(5)

    async def translate_text_to_srt(self, text: str, target_lang: str) -> str:
        """Translate plain text or existing SRT into a precise SRT format with timestamps."""
        client = await self._get_next_client()
        if not client: return ""

        prompt = f"""You are a professional video translator. Translate the following content into {target_lang}.
        If the input is plain text, generate appropriate SRT timestamps based on natural speech pacing (approx 150 words per minute).
        If the input is SRT, maintain the exact timestamps but translate the text accurately.
        
        OUTPUT FORMAT: Strict SRT format.
        """
        
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_model,
                contents=f"{prompt}\n\nCONTENT:\n{text}",
                config=types.GenerateContentConfig(temperature=0.3)
            )
            return response.text.strip()
        except Exception as e:
            print(f"Translation error: {e}")
            return ""

    async def rewrite_to_fit_duration(self, original_text: str, current_text: str, target_duration: float, current_duration: float, lang: str) -> str:
        """Rewrite text to fit duration, providing context of the previous attempt."""
        client = await self._get_next_client()
        if not client: return current_text

        diff = current_duration - target_duration
        action = "shorten" if diff > 0 else "lengthen"
        
        prompt = f"""
        Target Duration: {target_duration:.2f}s
        Current Duration: {current_duration:.2f}s
        Language: {lang}
        
        Original Meaning: {original_text}
        Last Attempt: {current_text}
        
        The last attempt was too {"long" if diff > 0 else "short"}. Please {action} the text while keeping the original meaning.
        Provide ONLY the rewritten text. No explanations.
        """
        
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7)
            )
            return response.text.strip()
        except Exception:
            return current_text
