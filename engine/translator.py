import re
import asyncio
import time
from typing import List
import google.generativeai as genai

class Translator:
    def __init__(self, api_keys: List[str] = None, max_rpm: int = 9):
        self.api_keys = api_keys if api_keys else []
        self.max_rpm = max_rpm
        self.current_key_index = 0
        self.api_lock = asyncio.Lock()
        self.key_usage = {key: [] for key in self.api_keys}
        # Using the model name requested by the user
        self.gemini_model_name = 'gemini-3.5-flash'

    def _setup_genai(self, api_key: str):
        genai.configure(api_key=api_key)
        # Setting API version to v1beta as suggested in the screenshot
        return genai.GenerativeModel(self.gemini_model_name)

    async def _get_next_model(self):
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
                return self._setup_genai(key)
            await asyncio.sleep(5)

    async def translate_text_to_srt(self, text: str, target_lang: str) -> str:
        model = await self._get_next_model()
        if not model: return ""

        prompt = f"""You are a professional video translator. Translate the following content into {target_lang}.
        
        GUIDELINES:
        1. If the input is plain text, you MUST generate appropriate SRT timestamps (e.g., 00:00:00,000 --> 00:00:05,000) based on natural speech pacing.
        2. If the input is already in SRT format, you MUST maintain the exact same timestamps but translate the text.
        3. The output MUST be in valid SRT format only.
        4. Do not include any preamble, markdown code blocks (like ```srt), or explanations.
        
        TARGET LANGUAGE: {target_lang}
        """
        
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                f"{prompt}\n\nCONTENT TO TRANSLATE:\n{text}"
            )
            clean_text = response.text.strip()
            clean_text = re.sub(r'^```srt\n', '', clean_text)
            clean_text = re.sub(r'\n```$', '', clean_text)
            return clean_text.strip()
        except Exception as e:
            return f"ERROR: {str(e)}"

    async def rewrite_to_fit_duration(self, original_text: str, current_text: str, target_duration: float, current_duration: float, lang: str) -> str:
        model = await self._get_next_model()
        if not model: return current_text

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
                model.generate_content,
                prompt
            )
            return response.text.strip()
        except Exception:
            return current_text
