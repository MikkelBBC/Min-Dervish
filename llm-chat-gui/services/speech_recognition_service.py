"""
Speech Recognition Service
"""
import speech_recognition as sr
from typing import Optional, Tuple
import threading
import config

class SpeechRecognitionService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone: Optional[sr.Microphone] = None
        self.is_listening = False
        self.is_initialized = False
        
    def init_microphone(self) -> Tuple[bool, str]:
        """Initialiser mikrofon"""
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(
                    source, 
                    duration=config.SPEECH_ADJUST_DURATION
                )
            self.is_initialized = True
            return True, "✅ Mikrofon klar"
        except Exception as e:
            self.microphone = None
            self.is_initialized = False
            return False, f"❌ Mikrofon fejl: {str(e)[:30]}"
    
    def listen_for_speech(self, callback):
        """Start lytning efter tale (non-blocking)"""
        if self.is_listening or not self.is_initialized:
            return False
        
        if not self.microphone:
            return False
        
        self.is_listening = True
        threading.Thread(
            target=self._listen_thread, 
            args=(callback,), 
            daemon=True
        ).start()
        return True
    
    def _listen_thread(self, callback):
        """Tråd funktion for speech recognition"""
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source, 
                    timeout=config.SPEECH_TIMEOUT, 
                    phrase_time_limit=config.SPEECH_PHRASE_LIMIT
                )
            
            # Prøv dansk først, så engelsk
            text = None
            try:
                text = self.recognizer.recognize_google(audio, language="da-DK")
            except:
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                except:
                    pass
            
            callback(text)
            
        except Exception as e:
            print(f"Speech recognition error: {e}")
            callback(None)
        finally:
            self.is_listening = False
    
    def is_available(self) -> bool:
        """Check om speech recognition er tilgængelig"""
        return self.is_initialized and self.microphone is not None
    
    def is_currently_listening(self) -> bool:
        """Check om der lyttes lige nu"""
        return self.is_listening