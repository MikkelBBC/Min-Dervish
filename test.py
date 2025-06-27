import requests
import json
import pyttsx3
import speech_recognition as sr
import time
from datetime import datetime

class SimpleLLMChat:
    def __init__(self, llm_url="http://localhost:1234/v1/chat/completions"):
        self.llm_url = llm_url
        self.conversation_history = []
        self.system_prompt = {
            "role": "system",
            "content": "Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise."
        }
        self.conversation_history.append(self.system_prompt)
        
        # Initialiser TTS - mere simpel tilgang
        self.tts_engine = None
        self.tts_enabled = True
        self.init_tts()
        
        # Initialiser Speech Recognition
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.init_microphone()
    
    def init_tts(self):
        """Initialiser TTS engine"""
        try:
            self.tts_engine = pyttsx3.init()
            
            # Indstil hastighed og lydstyrke
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            
            # Prøv at finde dansk stemme
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if any(lang in voice.id.lower() for lang in ['danish', 'dansk', 'da_dk', 'da-dk']):
                    self.tts_engine.setProperty('voice', voice.id)
                    print(f"✅ Dansk stemme fundet: {voice.name}")
                    break
            else:
                print("⚠️ Ingen dansk stemme fundet, bruger standard")
            
            print("✅ TTS initialiseret")
        except Exception as e:
            print(f"❌ TTS fejl: {e}")
            self.tts_engine = None
    
    def speak(self, text):
        """Læs tekst højt - SIMPEL VERSION"""
        if not self.tts_enabled or not self.tts_engine or not text.strip():
            return
        
        try:
            print("🔊 Læser højt...")
            # Stop eventuel igangværende tale først
            self.tts_engine.stop()
            # Kort pause
            time.sleep(0.2)
            # Læs det nye
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            print("✅ Færdig med at læse")
        except Exception as e:
            print(f"❌ TTS fejl: {e}")
    
    def init_microphone(self):
        """Initialiser mikrofon"""
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                print("🎤 Kalibrerer mikrofon...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ Mikrofon klar")
        except Exception as e:
            print(f"❌ Mikrofon fejl: {e}")
            self.microphone = None
    
    def listen(self):
        """Lyt efter tale"""
        if not self.microphone:
            print("❌ Ingen mikrofon tilgængelig")
            return None
        
        try:
            with self.microphone as source:
                print("🎤 Lytter... (tal nu)")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("🔄 Genkender tale...")
            
            # Prøv dansk først
            try:
                text = self.recognizer.recognize_google(audio, language="da-DK")
                print(f"✅ Genkendt (dansk): {text}")
                return text
            except:
                # Fald tilbage til engelsk
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    print(f"✅ Genkendt (engelsk): {text}")
                    return text
                except:
                    print("❌ Kunne ikke genkende tale")
                    return None
        except Exception as e:
            print(f"❌ Lyttefejl: {e}")
            return None
    
    def chat_with_llm(self, prompt):
        """Send forespørgsel til LLM - SIMPEL VERSION UDEN STREAMING"""
        headers = {"Content-Type": "application/json"}
        
        # Tilføj brugerens besked
        self.conversation_history.append({"role": "user", "content": prompt})
        
        # Begræns historik
        messages = [self.system_prompt] + self.conversation_history[-10:]
        
        data = {
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 300,
            "stream": False  # INGEN STREAMING for at undgå problemer
        }
        
        try:
            print("🤖 Sender forespørgsel...")
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            assistant_response = result['choices'][0]['message']['content']
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            print(f"🤖 LLM: {assistant_response}")
            return assistant_response
            
        except requests.exceptions.ConnectionError:
            error_msg = "Kan ikke forbinde til LLM. Er LM Studio kørende?"
            print(f"❌ {error_msg}")
            # Fjern brugerbesked ved fejl
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return error_msg
        except Exception as e:
            error_msg = f"Fejl: {e}"
            print(f"❌ {error_msg}")
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return error_msg
    
    def print_help(self):
        """Vis hjælpekommandoer"""
        print("\n📋 Kommandoer:")
        print("  'exit'    - Afslut")
        print("  'voice'   - Brug stemme")
        print("  'mute'    - TTS til/fra")
        print("  'clear'   - Ryd historik")
        print("  'help'    - Denne hjælp")
        print("-" * 30)
    
    def run(self):
        """Hovedloop - FORENKLET"""
        print("\n🎙️ Simpel LLM Chat med TTS")
        print("=" * 40)
        self.print_help()
        
        try:
            while True:
                # Få input
                user_input = input(f"\n💬 Du: ").strip()
                
                # Håndter kommandoer
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Farvel!")
                    break
                
                elif user_input.lower() == 'voice':
                    voice_input = self.listen()
                    if voice_input:
                        user_input = voice_input
                        print(f"📝 Du sagde: {user_input}")
                    else:
                        continue
                
                elif user_input.lower() == 'mute':
                    self.tts_enabled = not self.tts_enabled
                    print(f"🔊 TTS: {'TIL' if self.tts_enabled else 'FRA'}")
                    continue
                
                elif user_input.lower() == 'clear':
                    self.conversation_history = [self.system_prompt]
                    print("🧹 Historik ryddet")
                    continue
                
                elif user_input.lower() == 'help':
                    self.print_help()
                    continue
                
                elif not user_input:
                    continue
                
                # Send til LLM
                response = self.chat_with_llm(user_input)
                
                # Læs højt EFTER LLM svaret er færdigt
                if response and response.strip():
                    # Vent lidt for at sikre alt er klar
                    time.sleep(0.5)
                    self.speak(response)
        
        except KeyboardInterrupt:
            print("\n👋 Afbrudt - farvel!")
        except Exception as e:
            print(f"❌ Uventet fejl: {e}")

def test_connection():
    """Test LLM forbindelse"""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=3)
        if response.status_code == 200:
            print("✅ LLM forbindelse OK")
            return True
    except:
        pass
    
    print("❌ Kan ikke forbinde til LLM")
    print("💡 Start LM Studio og load en model")
    return False

if __name__ == "__main__":
    print("🚀 Starter simpel LLM Chat...")
    
    # Test forbindelse
    if not test_connection():
        input("Tryk Enter for at fortsætte alligevel...")
    
    # Start chat
    chat = SimpleLLMChat()
    chat.run()