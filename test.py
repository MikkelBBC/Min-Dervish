import requests
import json
import pyttsx3
import speech_recognition as sr
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

class LLMChatGUI:
    def __init__(self, llm_url="http://localhost:1234/v1/chat/completions"):
        # Hvis LM Studio kører på anden port, ændr 1234 til den korrekte port
        self.llm_url = llm_url
        self.conversation_history = []
        # System prompts
        self.danish_prompt = "Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise."
        self.english_prompt = "You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. Keep responses concise and clear."
        
        self.system_prompt = {
            "role": "system",
            "content": self.danish_prompt
        }
        self.conversation_history.append(self.system_prompt)
        
        # TTS og Speech Recognition
        self.tts_engine = None
        self.tts_enabled = True
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        
        # GUI setup
        self.setup_gui()
        self.init_tts()
        self.init_microphone()
        
        # Test forbindelse ved start
        self.test_connection()
    
    def setup_gui(self):
        """Opret GUI vindue"""
        self.root = tk.Tk()
        self.root.title("🤖 LLM Chat med TTS")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        
        # Hovedframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Chat display område
        chat_frame = ttk.LabelFrame(main_frame, text="💬 Samtale", padding="5")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            height=20,
            font=("Arial", 11),
            bg="white",
            fg="black"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Input område
        input_frame = ttk.LabelFrame(main_frame, text="✏️ Skriv besked", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Input felt og knapper
        input_row = ttk.Frame(input_frame)
        input_row.pack(fill=tk.X)
        
        self.input_entry = tk.Text(input_row, height=3, font=("Arial", 11))
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Bind Enter key (Ctrl+Enter for at sende)
        self.input_entry.bind("<Control-Return>", lambda e: self.send_message())
        
        button_frame = ttk.Frame(input_row)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.send_button = ttk.Button(
            button_frame, 
            text="📤 Send", 
            command=self.send_message,
            width=10
        )
        self.send_button.pack(fill=tk.X, pady=(0, 5))
        
        self.voice_button = ttk.Button(
            button_frame, 
            text="🎤 Tal", 
            command=self.toggle_voice_input,
            width=10
        )
        self.voice_button.pack(fill=tk.X, pady=(0, 5))
        
        # Kontrol panel
        control_frame = ttk.LabelFrame(main_frame, text="🎛️ Kontroller", padding="5")
        control_frame.pack(fill=tk.X)
        
        controls_row = ttk.Frame(control_frame)
        controls_row.pack(fill=tk.X)
        
        # TTS og engelsk response toggle
        self.tts_var = tk.BooleanVar(value=True)
        self.tts_checkbox = ttk.Checkbutton(
            controls_row, 
            text="🔊 Oplæsning", 
            variable=self.tts_var,
            command=self.toggle_tts
        )
        self.tts_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
        # English response toggle
        self.english_var = tk.BooleanVar(value=False)
        self.english_checkbox = ttk.Checkbutton(
            controls_row, 
            text="🇬🇧 Engelsk svar", 
            variable=self.english_var,
            command=self.toggle_english_response
        )
        self.english_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
        # Clear chat
        ttk.Button(
            controls_row, 
            text="🧹 Ryd chat", 
            command=self.clear_chat
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Status
        self.status_label = ttk.Label(controls_row, text="🟡 Starter...")
        self.status_label.pack(side=tk.RIGHT)
        
        # Tilføj velkomstbesked
        self.add_to_chat("System", "Velkommen! Skriv en besked eller brug 🎤 Tal knappen.\nCtrl+Enter for at sende besked.", "system")
    
    def init_tts(self):
        """Initialiser TTS engine"""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            
            # Prøv at finde dansk stemme
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if any(lang in voice.id.lower() for lang in ['danish', 'dansk', 'da_dk', 'da-dk']):
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            self.update_status("✅ TTS klar")
        except Exception as e:
            self.update_status(f"❌ TTS fejl: {str(e)[:30]}")
            self.tts_engine = None
    
    def init_microphone(self):
        """Initialiser mikrofon"""
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.update_status("✅ Mikrofon klar")
        except Exception as e:
            self.update_status(f"❌ Mikrofon fejl: {str(e)[:30]}")
            self.microphone = None
    
    def test_connection(self):
        """Test LLM forbindelse"""
        def test():
            try:
                response = requests.get("http://localhost:1234/v1/models", timeout=3)
                if response.status_code == 200:
                    models = response.json()
                    model_count = len(models.get('data', []))
                    self.update_status(f"✅ LLM forbundet ({model_count} modeller)")
                else:
                    self.update_status(f"❌ LLM fejl: HTTP {response.status_code}")
            except requests.exceptions.ConnectionError:
                self.update_status("❌ LM Studio ikke startet")
            except Exception as e:
                self.update_status(f"❌ Forbindelsesfejl: {str(e)[:20]}")
        
        threading.Thread(target=test, daemon=True).start()
    
    def update_status(self, message):
        """Opdater status label"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    def add_to_chat(self, sender, message, msg_type="user"):
        """Tilføj besked til chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Timestamp
        timestamp = datetime.now().strftime("%H:%M")
        
        # Farver baseret på type
        if msg_type == "system":
            self.chat_display.insert(tk.END, f"[{timestamp}] {sender}: ", "system_sender")
            self.chat_display.insert(tk.END, f"{message}\n\n", "system_msg")
        elif msg_type == "user":
            self.chat_display.insert(tk.END, f"[{timestamp}] Du: ", "user_sender")
            self.chat_display.insert(tk.END, f"{message}\n", "user_msg")
        else:  # assistant
            self.chat_display.insert(tk.END, f"[{timestamp}] 🤖 Assistant: ", "assistant_sender")
            self.chat_display.insert(tk.END, f"{message}\n\n", "assistant_msg")
        
        # Scroll til bunden
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
        # Konfigurer tags for farver
        self.chat_display.tag_config("system_sender", foreground="purple", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("system_msg", foreground="purple")
        self.chat_display.tag_config("user_sender", foreground="blue", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("user_msg", foreground="black")
        self.chat_display.tag_config("assistant_sender", foreground="green", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("assistant_msg", foreground="dark green")
    
    def send_message(self):
        """Send besked til LLM"""
        message = self.input_entry.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Ryd input felt
        self.input_entry.delete("1.0", tk.END)
        
        # Tilføj til chat
        self.add_to_chat("Du", message, "user")
        
        # Disable send button mens vi venter
        self.send_button.config(state=tk.DISABLED, text="⏳ Sender...")
        
        # Send i baggrunden
        threading.Thread(target=self._send_to_llm, args=(message,), daemon=True).start()
    
    def _send_to_llm(self, prompt):
        """Send forespørgsel til LLM (kører i baggrunden)"""
        try:
            headers = {"Content-Type": "application/json"}
            
            # Tilføj til historie
            self.conversation_history.append({"role": "user", "content": prompt})
            
            # Begræns historik
            messages = [self.system_prompt] + self.conversation_history[-10:]
            
            data = {
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 300,
                "stream": False
            }
            
            self.update_status("🤖 Tænker...")
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            assistant_response = result['choices'][0]['message']['content']
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            # Opdater GUI i main thread
            self.root.after(0, self._handle_llm_response, assistant_response)
            
        except requests.exceptions.ConnectionError:
            error_msg = "Kan ikke forbinde til LLM. Er LM Studio kørende?"
            self.root.after(0, self._handle_llm_error, error_msg)
        except Exception as e:
            error_msg = f"Fejl: {str(e)}"
            self.root.after(0, self._handle_llm_error, error_msg)
    
    def _handle_llm_response(self, response):
        """Håndter LLM respons (kører i main thread)"""
        self.add_to_chat("Assistant", response, "assistant")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("✅ Klar")
        
        # Oplæs hvis aktiveret
        if self.tts_var.get() and self.tts_engine:
            threading.Thread(target=self._speak, args=(response,), daemon=True).start()
    
    def _handle_llm_error(self, error_msg):
        """Håndter LLM fejl (kører i main thread)"""
        self.add_to_chat("System", error_msg, "system")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("❌ Fejl")
        
        # Fjern sidste brugerbesked ved fejl
        if self.conversation_history and self.conversation_history[-1]["role"] == "user":
            self.conversation_history.pop()
    
    def _speak(self, text):
        """Oplæs tekst (kører i baggrunden)"""
        try:
            if self.tts_engine and text.strip():
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS fejl: {e}")
    
    def toggle_voice_input(self):
        """Toggle stemme input"""
        if self.is_listening:
            return
        
        if not self.microphone:
            messagebox.showerror("Fejl", "Mikrofon ikke tilgængelig")
            return
        
        self.voice_button.config(state=tk.DISABLED, text="🎤 Lytter...")
        threading.Thread(target=self._listen_for_voice, daemon=True).start()
    
    def _listen_for_voice(self):
        """Lyt efter stemme input (kører i baggrunden)"""
        try:
            self.is_listening = True
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            # Prøv dansk først, så engelsk
            try:
                text = self.recognizer.recognize_google(audio, language="da-DK")
            except:
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                except:
                    text = None
            
            # Opdater GUI i main thread
            self.root.after(0, self._handle_voice_result, text)
            
        except Exception as e:
            self.root.after(0, self._handle_voice_result, None)
        finally:
            self.is_listening = False
    
    def _handle_voice_result(self, text):
        """Håndter stemme resultat (kører i main thread)"""
        self.voice_button.config(state=tk.NORMAL, text="🎤 Tal")
        
        if text:
            self.input_entry.insert(tk.END, text)
            self.add_to_chat("System", f"Genkendt: {text}", "system")
        else:
            self.add_to_chat("System", "Kunne ikke genkende tale. Prøv igen.", "system")
    
    def toggle_english_response(self):
        """Toggle engelsk respons mode"""
        if self.english_var.get():
            # Skift til engelsk system prompt
            self.system_prompt["content"] = self.english_prompt
            self.update_status("🇬🇧 Engelsk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på engelsk selvom du skriver dansk.", "system")
        else:
            # Skift tilbage til dansk system prompt
            self.system_prompt["content"] = self.danish_prompt
            self.update_status("🇩🇰 Dansk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på dansk igen.", "system")
        
        # Opdater system prompt i samtale historik
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0] = self.system_prompt.copy()
    
    def toggle_tts(self):
        """Toggle TTS"""
        self.tts_enabled = self.tts_var.get()
        status = "TIL" if self.tts_enabled else "FRA"
        self.update_status(f"🔊 TTS: {status}")
    
    def clear_chat(self):
        """Ryd chat historie"""
        self.conversation_history = [self.system_prompt]
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.add_to_chat("System", "Chat ryddet. Start en ny samtale!", "system")
    
    def run(self):
        """Start GUI"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

def main():
    """Hovedfunktion"""
    print("🚀 Starter LLM Chat GUI...")
    app = LLMChatGUI()
    app.run()

if __name__ == "__main__":
    main()