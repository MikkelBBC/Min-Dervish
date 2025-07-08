"""
Audio håndtering (TTS og Speech Recognition) for LLM Chat applikationen
"""
import pyttsx3
import speech_recognition as sr
import threading
from config import Config

class AudioManager:
    """Håndterer TTS og Speech Recognition"""
    
    def __init__(self):
        self.tts_engine = None
        self.tts_enabled = True
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        
        # Callbacks for status updates
        self.on_status_update = None
        self.on_voice_result = None
        
        self.init_tts()
        self.init_microphone()
    
    def set_callbacks(self, on_status_update=None, on_voice_result=None):
        """Sæt callback funktioner"""
        self.on_status_update = on_status_update
        self.on_voice_result = on_voice_result
    
    def init_tts(self):
        """Initialiser TTS engine"""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', Config.TTS_RATE)
            self.tts_engine.setProperty('volume', Config.TTS_VOLUME)
            
            # Prøv at finde dansk stemme
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if any(lang in voice.id.lower() for lang in ['danish', 'dansk', 'da_dk', 'da-dk']):
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            if self.on_status_update:
                self.on_status_update("✅ TTS klar")
            return True
        except Exception as e:
            if self.on_status_update:
                self.on_status_update(f"❌ TTS fejl: {str(e)[:30]}")
            self.tts_engine = None
            return False
    
    def init_microphone(self):
        """Initialiser mikrofon"""
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            if self.on_status_update:
                self.on_status_update("✅ Mikrofon klar")
            return True
        except Exception as e:
            if self.on_status_update:
                self.on_status_update(f"❌ Mikrofon fejl: {str(e)[:30]}")
            self.microphone = None
            return False
    
    def set_tts_enabled(self, enabled):
        """Sæt TTS til/fra"""
        self.tts_enabled = enabled
    
    def is_tts_available(self):
        """Tjek om TTS er tilgængelig"""
        return self.tts_engine is not None
    
    def is_microphone_available(self):
        """Tjek om mikrofon er tilgængelig"""
        return self.microphone is not None
    
    def speak(self, text):
        """Oplæs tekst (asynkront)"""
        if self.tts_enabled and self.tts_engine and text.strip():
            threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()
    
    def _speak_sync(self, text):
        """Oplæs tekst (synkront - kører i baggrunden)"""
        try:
            if self.tts_engine and text.strip():
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS fejl: {e}")
    
    def start_voice_input(self):
        """Start stemme input"""
        if self.is_listening:
            return False
        
        if not self.microphone:
            if self.on_voice_result:
                self.on_voice_result(None, "Mikrofon ikke tilgængelig")
            return False
        
        threading.Thread(target=self._listen_for_voice, daemon=True).start()
        return True
    
    def _listen_for_voice(self):
        """Lyt efter stemme input (kører i baggrunden)"""
        try:
            self.is_listening = True
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            # Prøv dansk først, så engelsk
            text = None
            try:
                text = self.recognizer.recognize_google(audio, language="da-DK")
            except:
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                except:
                    pass
            
            # Returner resultat via callback
            if self.on_voice_result:
                if text:
                    self.on_voice_result(text, None)
                else:
                    self.on_voice_result(None, "Kunne ikke genkende tale")
            
        except sr.WaitTimeoutError:
            if self.on_voice_result:
                self.on_voice_result(None, "Timeout - ingen tale opdaget")
        except Exception as e:
            if self.on_voice_result:
                self.on_voice_result(None, f"Fejl: {str(e)}")
        finally:
            self.is_listening = False
    
    def stop_listening(self):
        """Stop lytning (bruges til at afbryde hvis nødvendigt)"""
        self.is_listening = False