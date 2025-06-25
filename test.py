import requests
import json
import pyttsx3
import threading
import queue
import time

class TTSManager:
    def __init__(self):
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        self.running = True
        self.engine = None
        self.init_engine()
        self.start_worker()
    
    def init_engine(self):
        """Initialiser TTS engine"""
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            
            # Vælg dansk stemme hvis muligt
            for voice in voices:
                if 'danish' in voice.name.lower() or 'dk' in voice.id.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
            
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 0.9)
        except Exception as e:
            print(f"TTS initialisering fejlede: {e}")
    
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
                    self.engine.say(text)
                    self.engine.runAndWait()
                
                self.tts_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS fejl: {e}")
                # Prøv at geninitialisere
                self.init_engine()
    
    def speak(self, text):
        """Tilføj tekst til TTS queue"""
        try:
            # Ryd køen hvis den er fuld
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.tts_queue.put(text)
        except Exception as e:
            print(f"Kunne ikke tilføje til TTS queue: {e}")
    
    def stop(self):
        """Stop TTS manager"""
        self.running = False
        self.tts_queue.put(None)  # Shutdown signal

class LLMChatWithTTS:
    def __init__(self):
        self.tts_manager = TTSManager()
        self.conversation_history = []  # Gem samtalehistorik
    
    def chat_with_codellama(self, prompt):
        """Send forespørgsel til LLM med samtalehistorik"""
        url = "http://localhost:1234/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Tilføj brugerens nye besked til historikken
        self.conversation_history.append({"role": "user", "content": prompt})
        
        data = {
            "messages": self.conversation_history,  # Send hele samtalehistorikken
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False
        }
        
        try:
            print("🤖 Sender forespørgsel...")
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # Gem assistentens svar i historikken
            assistant_response = result['choices'][0]['message']['content']
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
        except Exception as e:
            # Fjern den sidste brugerbesked hvis der var en fejl
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return f"Fejl: {e}"
    
    def clear_history(self):
        """Ryd samtalehistorik"""
        self.conversation_history = []
        print("🧹 Samtalehistorik ryddet")
    
    def show_history(self):
        """Vis samtalehistorik"""
        if not self.conversation_history:
            print("📝 Ingen samtalehistorik")
            return
        
        print("📝 Samtalehistorik:")
        for i, msg in enumerate(self.conversation_history):
            role = "Du" if msg["role"] == "user" else "LLM"
            print(f"{i+1}. {role}: {msg['content'][:100]}...")
    
    def save_history(self, filename="samtale_historik.json"):
        """Gem samtalehistorik til fil"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
            print(f"💾 Samtalehistorik gemt til {filename}")
        except Exception as e:
            print(f"❌ Kunne ikke gemme historik: {e}")
    
    def load_history(self, filename="samtale_historik.json"):
        """Indlæs samtalehistorik fra fil"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"📂 Samtalehistorik indlæst fra {filename}")
        except Exception as e:
            print(f"❌ Kunne ikke indlæse historik: {e}")
    
    def interactive_chat(self):
        """Hovedloop for interaktiv chat"""
        print("🎙️ LLM Chat med Text-to-Speech og Hukommelse")
        print("Kommandoer:")
        print("  'exit' - Afslut programmet")
        print("  'mute' - Slå TTS til/fra")
        print("  'skip' - Spring TTS over")
        print("  'clear' - Ryd samtalehistorik")
        print("  'history' - Vis samtalehistorik")
        print("  'save' - Gem samtalehistorik")
        print("  'load' - Indlæs samtalehistorik")
        print("-" * 50)
        
        tts_enabled = True
        
        try:
            while True:
                try:
                    # Få input fra bruger
                    user_input = input(f"\n💬 Du [{len(self.conversation_history)//2 + 1}]: ").strip()
                    
                    # Tjek for kommandoer
                    if user_input.lower() == 'exit':
                        print("👋 Farvel!")
                        break
                    elif user_input.lower() == 'mute':
                        tts_enabled = not tts_enabled
                        status = "slået til" if tts_enabled else "slået fra"
                        print(f"🔊 Text-to-speech er nu {status}")
                        continue
                    elif user_input.lower() == 'skip':
                        # Ryd TTS køen
                        while not self.tts_manager.tts_queue.empty():
                            try:
                                self.tts_manager.tts_queue.get_nowait()
                            except queue.Empty:
                                break
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
                        self.load_history()
                        continue
                    elif not user_input:
                        continue
                    
                    # Send til LLM
                    response = self.chat_with_codellama(user_input)
                    
                    # Vis svar
                    print(f"\n🤖 LLM: {response}")
                    
                    # Læs højt hvis aktiveret
                    if tts_enabled:
                        print("🔊 Tilføjer til TTS queue...")
                        self.tts_manager.speak(response)
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Chat afbrudt. Farvel!")
                    break
                except Exception as e:
                    print(f"❌ Uventet fejl: {e}")
        
        finally:
            # Ryd op
            self.tts_manager.stop()

# Hovedprogram
if __name__ == "__main__":
    chat = LLMChatWithTTS()
    chat.interactive_chat()