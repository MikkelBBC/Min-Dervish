"""
Text-to-Speech Service
"""
import pyttsx3
from typing import Optional, Tuple
import threading
import config

class TTSService:
    def __init__(self):
        self.engine: Optional[pyttsx3.Engine] = None
        self.enabled = True
        self.is_initialized = False
        
    def init_engine(self) -> Tuple[bool, str]:
        """Initialiser TTS engine"""
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', config.TTS_RATE)
            self.engine.setProperty('volume', config.TTS_VOLUME)
            
            # Prøv at finde dansk stemme
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if any(lang in voice.id.lower() for lang in config.DANISH_VOICE_IDENTIFIERS):
                    self.engine.setProperty('voice', voice.id)
                    break
            
            self.is_initialized = True
            return True, "✅ TTS klar"
        except Exception as e:
            self.engine = None
            self.is_initialized = False
            return False, f"❌ TTS fejl: {str(e)[:30]}"
    
    def speak(self, text: str):
        """Oplæs tekst i baggrunden"""
        if self.engine and self.enabled and text.strip() and self.is_initialized:
            threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()
    
    def _speak_thread(self, text: str):
        """Tråd funktion for TTS"""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"TTS fejl: {e}")
    
    def toggle(self, enabled: bool):
        """Toggle TTS on/off"""
        self.enabled = enabled
    
    def is_enabled(self) -> bool:
        """Check om TTS er aktiveret"""
        return self.enabled and self.is_initialized
    
    def cleanup(self):
        """Cleanup TTS engine"""
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass