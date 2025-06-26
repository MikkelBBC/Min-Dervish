import requests
import json
import pyttsx3
import threading
import queue
import time
import speech_recognition as sr
import os
import sys
from datetime import datetime
import wave
import pyaudio

class TTSManager:
    def __init__(self):
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        self.running = True
        self.engine = None
        self.is_speaking = False
        self.init_engine()
        self.start_worker()
    
    def init_engine(self):
        """Initialiser TTS engine med bedre fejlhåndtering"""
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            
            # Vælg dansk stemme hvis muligt
            danish_voice_found = False
            for voice in voices:
                if any(lang in voice.id.lower() for lang in ['danish', 'dansk', 'da_dk', 'da-dk']):
                    self.engine.setProperty('voice', voice.id)
                    danish_voice_found = True
                    print(f"✅ Dansk stemme fundet: {voice.name}")
                    break
            
            if not danish_voice_found:
                print("⚠️ Ingen dansk stemme fundet, bruger standard")
            
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 0.9)
        except Exception as e:
            print(f"❌ TTS initialisering fejlede: {e}")
            self.engine = None
    
    def start_worker(self):
        """Start worker thread til TTS"""
        self.tts_thread = threading.Thread(target=self._tts_worker)
        self.tts_thread.daemon = True
        self.tts_thread.start()
    
    def _tts_worker(self):
        """TTS worker der behandler queue"""
        while self.running:
            try:
                text = self.tts_queue.get(timeout=1)
                if text is None:  # Shutdown signal
                    break
                
                if self.engine:
                    self.is_speaking = True
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self.is_speaking = False
                
                self.tts_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ TTS fejl: {e}")
                self.is_speaking = False
                # Prøv at geninitialisere
                time.sleep(1)
                self.init_engine()
    
    def speak(self, text):
        """Tilføj tekst til TTS queue"""
        try:
            # Debug info
            print(f"📢 TTS: Tilføjer {len(text)} tegn til køen")
            self.tts_queue.put(text)
            print(f"📊 TTS kø størrelse: {self.tts_queue.qsize()}")
        except Exception as e:
            print(f"❌ Kunne ikke tilføje til TTS queue: {e}")
    
    def clear_queue(self):
        """Ryd TTS køen"""
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break
    
    def stop(self):
        """Stop TTS manager"""
        self.running = False
        self.tts_queue.put(None)  # Shutdown signal
        if self.tts_thread:
            self.tts_thread.join(timeout=5)

class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.init_microphone()
        
    def init_microphone(self):
        """Initialiser mikrofon"""
        try:
            self.microphone = sr.Microphone()
            # Juster for baggrundsstøj
            with self.microphone as source:
                print("🎤 Kalibrerer mikrofon for baggrundsstøj...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print("✅ Mikrofon klar")
        except Exception as e:
            print(f"❌ Mikrofon fejl: {e}")
            self.microphone = None
    
    def listen(self, timeout=5, phrase_time_limit=10):
        """Lyt efter tale og konverter til tekst"""
        if not self.microphone:
            print("❌ Ingen mikrofon tilgængelig")
            return None
        
        try:
            with self.microphone as source:
                print("🎤 Lytter... (tal nu)")
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=phrase_time_limit
                )
                
            print("🔄 Genkender tale...")
            
            # Prøv dansk først, fald tilbage til engelsk
            try:
                text = self.recognizer.recognize_google(audio, language="da-DK")
                print(f"✅ Genkendt (dansk): {text}")
                return text
            except:
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    print(f"✅ Genkendt (engelsk): {text}")
                    return text
                except:
                    print("❌ Kunne ikke genkende tale")
                    return None
                    
        except sr.WaitTimeoutError:
            print("⏱️ Timeout - ingen tale detekteret")
            return None
        except Exception as e:
            print(f"❌ Fejl under talegenkendelse: {e}")
            return None

class LLMChatWithVoice:
    def __init__(self, llm_url="http://localhost:1234/v1/chat/completions"):
        self.llm_url = llm_url
        self.tts_manager = TTSManager()
        self.speech_recognizer = SpeechRecognizer()
        self.conversation_history = []
        self.system_prompt = {
            "role": "system",
            "content": "Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise."
        }
        self.conversation_history.append(self.system_prompt)
        
    def chat_with_llm(self, prompt, stream=False):
        """Send forespørgsel til LLM med streaming support"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Tilføj brugerens nye besked til historikken
        self.conversation_history.append({"role": "user", "content": prompt})
        
        # Begræns historik til sidste 20 beskeder + system prompt for bedre kontekst
        messages = [self.system_prompt] + self.conversation_history[-20:]
        
        data = {
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
            "stream": stream
        }
        
        try:
            print("🤖 Sender forespørgsel...")
            
            if stream:
                response = requests.post(self.llm_url, json=data, headers=headers, stream=True)
                response.raise_for_status()
                
                full_response = ""
                print("🤖 LLM: ", end="", flush=True)
                
                for line in response.iter_lines():
                    if line:
                        try:
                            line_text = line.decode('utf-8')
                            if line_text.startswith('data: '):
                                json_str = line_text[6:]
                                if json_str.strip() == '[DONE]':
                                    break
                                data = json.loads(json_str)
                                if 'choices' in data and len(data['choices']) > 0:
                                    content = data['choices'][0].get('delta', {}).get('content', '')
                                    if content:
                                        print(content, end="", flush=True)
                                        full_response += content
                        except:
                            continue
                
                print()  # Ny linje efter streaming
                
                # Gem assistentens svar
                self.conversation_history.append({"role": "assistant", "content": full_response})
                return full_response
            else:
                response = requests.post(self.llm_url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # Gem assistentens svar
                assistant_response = result['choices'][0]['message']['content']
                self.conversation_history.append({"role": "assistant", "content": assistant_response})
                
                return assistant_response
                
        except requests.exceptions.ConnectionError:
            error_msg = "Kan ikke forbinde til LLM. Er LM Studio kørende?"
            print(f"❌ {error_msg}")
            # Fjern den sidste brugerbesked
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return error_msg
        except Exception as e:
            error_msg = f"Fejl: {e}"
            print(f"❌ {error_msg}")
            # Fjern den sidste brugerbesked
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return error_msg
    
    def clear_history(self):
        """Ryd samtalehistorik (behold system prompt)"""
        self.conversation_history = [self.system_prompt]
        print("🧹 Samtalehistorik ryddet")
    
    def show_history(self):
        """Vis samtalehistorik"""
        if len(self.conversation_history) <= 1:
            print("📝 Ingen samtalehistorik")
            return
        
        print("\n📝 Samtalehistorik:")
        print("-" * 50)
        for i, msg in enumerate(self.conversation_history[1:], 1):  # Skip system prompt
            role = "Du" if msg["role"] == "user" else "LLM"
            preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            print(f"{i}. {role}: {preview}")
        print("-" * 50)
    
    def save_history(self, filename=None):
        """Gem samtalehistorik til fil"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"samtale_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history[1:], f, indent=2, ensure_ascii=False)
            print(f"💾 Samtalehistorik gemt til {filename}")
        except Exception as e:
            print(f"❌ Kunne ikke gemme historik: {e}")
    
    def load_history(self, filename):
        """Indlæs samtalehistorik fra fil"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
            self.conversation_history = [self.system_prompt] + loaded_history
            print(f"📂 Samtalehistorik indlæst fra {filename}")
        except Exception as e:
            print(f"❌ Kunne ikke indlæse historik: {e}")
    
    def print_help(self):
        """Vis hjælpekommandoer"""
        print("\n📋 Tilgængelige kommandoer:")
        print("  'exit/quit'  - Afslut programmet")
        print("  'voice/v'    - Brug stemmeindtastning")
        print("  'mute'       - Slå TTS til/fra")
        print("  'skip'       - Spring TTS over")
        print("  'clear'      - Ryd samtalehistorik")
        print("  'history'    - Vis samtalehistorik")
        print("  'save'       - Gem samtalehistorik")
        print("  'load'       - Indlæs samtalehistorik")
        print("  'status'     - Vis TTS status")
        print("  'help'       - Vis denne hjælp")
        print("-" * 50)
    
    def interactive_chat(self):
        """Hovedloop for interaktiv chat"""
        print("\n🎙️ LLM Chat med Stemmegenekendelse og Text-to-Speech")
        print("=" * 50)
        self.print_help()
        
        tts_enabled = True
        
        try:
            while True:
                try:
                    # Få input fra bruger
                    user_input = input(f"\n💬 Du [{len(self.conversation_history)//2}]: ").strip()
                    
                    # Tjek for kommandoer
                    if user_input.lower() in ['exit', 'quit']:
                        print("👋 Farvel!")
                        break
                        
                    elif user_input.lower() in ['voice', 'v']:
                        print("\n🎤 Stemmeindtastning aktiveret")
                        voice_input = self.speech_recognizer.listen()
                        if voice_input:
                            print(f"📝 Du sagde: {voice_input}")
                            user_input = voice_input
                        else:
                            print("❌ Ingen tale genkendt, prøv igen")
                            continue
                            
                    elif user_input.lower() == 'mute':
                        tts_enabled = not tts_enabled
                        status = "slået til" if tts_enabled else "slået fra"
                        print(f"🔊 Text-to-speech er nu {status}")
                        continue
                        
                    elif user_input.lower() == 'skip':
                        self.tts_manager.clear_queue()
                        print("⏭️ TTS sprunget over")
                        continue
                        
                    elif user_input.lower() == 'clear':
                        self.clear_history()
                        continue
                        
                    elif user_input.lower() == 'history':
                        self.show_history()
                        continue
                        
                    elif user_input.lower() == 'save':
                        self.save_history()
                        continue
                        
                    elif user_input.lower() == 'load':
                        filename = input("📁 Indtast filnavn: ").strip()
                        if filename:
                            self.load_history(filename)
                        continue
                        
                    elif user_input.lower() == 'status':
                        print(f"\n📊 Status:")
                        print(f"  TTS aktiveret: {tts_enabled}")
                        print(f"  TTS kø størrelse: {self.tts_manager.tts_queue.qsize()}")
                        print(f"  TTS taler nu: {self.tts_manager.is_speaking}")
                        print(f"  Samtalehistorik: {len(self.conversation_history)-1} beskeder")
                        continue
                        
                    elif user_input.lower() == 'help':
                        self.print_help()
                        continue
                        
                    elif not user_input:
                        continue
                    
                    # Send til LLM med streaming
                    response = self.chat_with_llm(user_input, stream=True)
                    
                    # Læs højt hvis aktiveret OG der er et svar
                    if tts_enabled and response and response.strip():
                        # Vent lidt for at sikre streaming er færdig
                        time.sleep(0.5)
                        print("🔊 Læser svaret højt...")
                        self.tts_manager.speak(response)
                    
                except KeyboardInterrupt:
                    print("\n\n⏸️ Afbrudt - tryk Enter for at fortsætte eller skriv 'exit' for at afslutte")
                    continue
                except Exception as e:
                    print(f"❌ Uventet fejl: {e}")
        
        finally:
            # Ryd op
            print("\n🧹 Rydder op...")
            self.tts_manager.stop()
            print("✅ Farvel!")

# Test forbindelse til LLM
def test_llm_connection(url="http://localhost:1234/v1/chat/completions"):
    """Test om LLM er tilgængelig"""
    try:
        response = requests.get(url.replace("/chat/completions", "/models"), timeout=5)
        if response.status_code == 200:
            print("✅ LLM forbindelse OK")
            return True
    except:
        pass
    
    print("❌ Kan ikke forbinde til LLM på", url)
    print("📝 Sørg for at LM Studio kører og modellen er loaded")
    return False

# Hovedprogram
if __name__ == "__main__":
    print("🚀 Starter LLM Chat...")
    
    # Test LLM forbindelse
    if not test_llm_connection():
        print("\n⚠️ Fortsætter alligevel - nogle funktioner virker måske ikke")
        input("Tryk Enter for at fortsætte...")
    
    # Installer manglende pakker hvis nødvendigt
    try:
        import speech_recognition as sr
    except ImportError:
        print("\n📦 Installerer speech_recognition...")
        os.system("pip install SpeechRecognition")
        import speech_recognition as sr
    
    try:
        import pyaudio
    except ImportError:
        print("\n📦 Installerer pyaudio...")
        os.system("pip install pyaudio")
        import pyaudio
    
    # Start chat
    chat = LLMChatWithVoice()
    chat.interactive_chat()