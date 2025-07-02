import requests
import json
import pyttsx3
import speech_recognition as sr
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import os
import pickle

class LLMChatGUI:
    def __init__(self, llm_url="http://localhost:1234/v1/chat/completions"):
        # Hvis LM Studio kører på anden port, ændr 1234 til den korrekte port
        self.llm_url = llm_url
        
        # Session management
        self.sessions = {}  # {session_id: {"name": str, "history": list, "created": datetime, "notes": str}}
        self.current_session_id = None
        self.sessions_file = "chat_sessions.pkl"
        self.user_notes_file = "user_notes.json"
        
        # Load eksisterende data
        self.load_sessions()
        self.load_user_notes()
        
        # System prompts
        self.danish_prompt = "Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise."
        self.english_prompt = "You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. Keep responses concise and clear."
        
        self.system_prompt = {
            "role": "system",
            "content": self.danish_prompt
        }
        
        # TTS og Speech Recognition
        self.tts_engine = None
        self.tts_enabled = True
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        
        # GUI setup FØRST
        self.setup_gui()
        
        # Start med ny session EFTER GUI er oprettet
        self.create_new_session()
        
        self.init_tts()
        self.init_microphone()
        
        # Test forbindelse ved start
        self.test_connection()
    
    def setup_gui(self):
        """Opret GUI vindue"""
        self.root = tk.Tk()
        self.root.title("🤖 LLM Chat med Sessions & AI Noter")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f0f0")
        
        # Hovedframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top panel med sessions og noter
        top_panel = ttk.Frame(main_frame)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        
        # Sessions panel (venstre)
        sessions_frame = ttk.LabelFrame(top_panel, text="📁 Samtaler", padding="5")
        sessions_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        sessions_controls = ttk.Frame(sessions_frame)
        sessions_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(sessions_controls, text="➕ Ny", command=self.create_new_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sessions_controls, text="💾 Gem", command=self.save_current_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sessions_controls, text="🗑️ Slet", command=self.delete_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        
        # Sessions liste
        self.sessions_listbox = tk.Listbox(sessions_frame, height=4, font=("Arial", 10))
        self.sessions_listbox.pack(fill=tk.BOTH, expand=True)
        self.sessions_listbox.bind('<Double-Button-1>', self.load_selected_session)
        
        # AI Noter panel (højre)
        notes_frame = ttk.LabelFrame(top_panel, text="🧠 AI Noter om dig", padding="5")
        notes_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        notes_controls = ttk.Frame(notes_frame)
        notes_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(notes_controls, text="🔄 Opdater noter", command=self.update_user_notes, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(notes_controls, text="👁️ Vis alle", command=self.show_full_notes, width=10).pack(side=tk.LEFT)
        
        self.notes_display = scrolledtext.ScrolledText(notes_frame, height=4, font=("Arial", 9), 
                                                      bg="#f9f9f9", fg="darkblue")
        self.notes_display.pack(fill=tk.BOTH, expand=True)
        
        # Chat display område
        chat_frame = ttk.LabelFrame(main_frame, text="💬 Samtale", padding="5")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            height=15,
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
        
        # Session navn
        self.session_name_label = ttk.Label(controls_row, text="📝 Aktuel: Ny samtale", 
                                           font=("Arial", 10, "italic"))
        self.session_name_label.pack(side=tk.LEFT, padx=(20, 10))
        
        # Status
        self.status_label = ttk.Label(controls_row, text="🟡 Starter...")
        self.status_label.pack(side=tk.RIGHT)
        
        # Opdater displays (kun hvis GUI er klar)
        if hasattr(self, 'sessions_listbox'):
            self.refresh_sessions_list()
            self.refresh_notes_display()
            
            # Tilføj velkomstbesked
            self.add_to_chat("System", "Velkommen! AI'en husker dig mellem samtaler og tager noter om dine præferencer.\nCtrl+Enter for at sende besked.", "system")
    
    # Session Management
    def create_new_session(self):
        """Opret ny session"""
        # Hvis GUI ikke er klar endnu, brug default
        if not hasattr(self, 'sessions_listbox'):
            session_name = f"Samtale {len(self.sessions) + 1}"
        else:
            session_name = simpledialog.askstring("Ny samtale", "Navn på samtale:", 
                                                 initialvalue=f"Samtale {len(self.sessions) + 1}")
            if not session_name:
                return
        
        session_id = str(int(time.time()))
        self.sessions[session_id] = {
            "name": session_name,
            "history": [self.system_prompt.copy()],
            "created": datetime.now(),
            "notes": ""
        }
        
        self.current_session_id = session_id
        self.conversation_history = self.sessions[session_id]["history"]
        
        # Kun opdater GUI hvis den eksisterer
        if hasattr(self, 'sessions_listbox'):
            self.refresh_sessions_list()
            self.clear_chat_display()
            self.update_session_label()
            self.add_to_chat("System", f"Ny samtale '{session_name}' oprettet!", "system")
    
    def load_selected_session(self, event=None):
        """Load valgt session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        if session_id in self.sessions:
            self.current_session_id = session_id
            self.conversation_history = self.sessions[session_id]["history"]
            self.refresh_chat_from_history()
            self.update_session_label()
    
    def save_current_session(self):
        """Gem aktuel session"""
        if self.current_session_id and self.current_session_id in self.sessions:
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
            self.save_sessions()
            self.add_to_chat("System", "Samtale gemt! 💾", "system")
        else:
            messagebox.showwarning("Advarsel", "Ingen aktuel samtale at gemme")
    
    def delete_session(self):
        """Slet valgt session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Vælg en samtale at slette")
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        if messagebox.askyesno("Bekræft", f"Slet samtale '{self.sessions[session_id]['name']}'?"):
            del self.sessions[session_id]
            if self.current_session_id == session_id:
                self.create_new_session()
            self.refresh_sessions_list()
            self.save_sessions()
    
    def refresh_sessions_list(self):
        """Opdater sessions liste"""
        # Tjek om GUI er klar
        if not hasattr(self, 'sessions_listbox'):
            return
            
        self.sessions_listbox.delete(0, tk.END)
        for session_id, session_data in sorted(self.sessions.items(), 
                                              key=lambda x: x[1]["created"], reverse=True):
            created_str = session_data["created"].strftime("%d/%m %H:%M")
            msg_count = len([msg for msg in session_data["history"] if msg["role"] == "user"])
            display_text = f"{session_id} - {session_data['name']} ({msg_count} beskeder, {created_str})"
            self.sessions_listbox.insert(0, display_text)
    
    def update_session_label(self):
        """Opdater session label"""
        if self.current_session_id and self.current_session_id in self.sessions:
            name = self.sessions[self.current_session_id]["name"]
            self.session_name_label.config(text=f"📝 Aktuel: {name}")
    
    def refresh_chat_from_history(self):
        """Genopbyg chat fra historie"""
        self.clear_chat_display()
        
        for msg in self.conversation_history:
            if msg["role"] == "user":
                self.add_to_chat("Du", msg["content"], "user")
            elif msg["role"] == "assistant":
                self.add_to_chat("Assistant", msg["content"], "assistant")
    
    def clear_chat_display(self):
        """Ryd kun chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    # AI Noter System
    def load_user_notes(self):
        """Load bruger noter"""
        try:
            if os.path.exists(self.user_notes_file):
                with open(self.user_notes_file, 'r', encoding='utf-8') as f:
                    self.user_notes = json.load(f)
            else:
                self.user_notes = {
                    "personality": "",
                    "preferences": "",
                    "interests": "",
                    "communication_style": "",
                    "technical_level": "",
                    "last_updated": ""
                }
        except:
            self.user_notes = {
                "personality": "",
                "preferences": "",
                "interests": "",
                "communication_style": "",
                "technical_level": "",
                "last_updated": ""
            }
    
    def save_user_notes(self):
        """Gem bruger noter"""
        try:
            with open(self.user_notes_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_notes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fejl ved gemning af noter: {e}")
    
    def update_user_notes(self):
        """Bed AI om at opdatere bruger noter"""
        if not self.conversation_history or len(self.conversation_history) < 3:
            messagebox.showinfo("Info", "For få beskeder til at opdatere noter. Chat lidt mere først!")
            return
        
        # Saml seneste samtale
        recent_messages = []
        for msg in self.conversation_history[-10:]:  # Sidste 10 beskeder
            if msg["role"] in ["user", "assistant"]:
                recent_messages.append(f"{msg['role']}: {msg['content']}")
        
        conversation_text = "\n".join(recent_messages)
        
        analysis_prompt = f"""Analyser denne samtale og opdater informationer om brugeren. Du SKAL svare med PRÆCIS dette JSON format - ingen ekstra tekst:

{{
    "personality": "kort beskrivelse af personlighed",
    "preferences": "præferencer og valg brugeren viser",
    "interests": "interesser og emner brugeren engagerer sig i",
    "communication_style": "hvordan brugeren kommunikerer",
    "technical_level": "teknisk niveau (begynder/mellemliggende/avanceret)",
    "last_updated": "{datetime.now().strftime('%Y-%m-%d %H:%M')}"
}}

Tidligere noter:
{json.dumps(self.user_notes, ensure_ascii=False)}

Seneste samtale:
{conversation_text}

VIGTIGT: Svar KUN med valid JSON - ingen forklaring eller ekstra tekst!
        
        # Send til AI i baggrunden
        threading.Thread(target=self._get_ai_notes_update, args=(analysis_prompt,), daemon=True).start()
        self.update_status("🧠 Opdaterer AI noter...")
    
    def _get_ai_notes_update(self, prompt):
        """Få AI til at opdatere noter (baggrund)"""
        try:
            headers = {"Content-Type": "application/json"}
            data = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Lavere temperatur for mere konsistente JSON svar
                "max_tokens": 400,
                "stream": False
            }
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=45)  # Længere timeout
            response.raise_for_status()
            result = response.json()
            
            ai_response = result['choices'][0]['message']['content'].strip()
            
            # Bedre JSON parsing
            try:
                # Fjern eventuelle markdown koder og whitespace
                ai_response = ai_response.replace('```json', '').replace('```', '').strip()
                
                # Find JSON start og slut
                start = ai_response.find('{')
                end = ai_response.rfind('}') + 1
                
                if start >= 0 and end > start:
                    json_str = ai_response[start:end]
                    updated_notes = json.loads(json_str)
                    
                    # Valider at alle nødvendige felter er der
                    required_fields = ["personality", "preferences", "interests", "communication_style", "technical_level", "last_updated"]
                    if all(field in updated_notes for field in required_fields):
                        # Opdater noter
                        self.user_notes.update(updated_notes)
                        self.save_user_notes()
                        
                        # Opdater GUI
                        self.root.after(0, self._handle_notes_update_success)
                    else:
                        self.root.after(0, self._handle_notes_update_error, "Manglende felter i AI svar")
                else:
                    self.root.after(0, self._handle_notes_update_error, "Ingen valid JSON fundet")
                    
            except json.JSONDecodeError as e:
                self.root.after(0, self._handle_notes_update_error, f"JSON parse fejl: {str(e)}")
                
        except requests.exceptions.Timeout:
            self.root.after(0, self._handle_notes_update_error, "Timeout - AI'en svarede ikke i tide")
        except requests.exceptions.ConnectionError:
            self.root.after(0, self._handle_notes_update_error, "Kan ikke forbinde til LLM")
        except Exception as e:
            self.root.after(0, self._handle_notes_update_error, f"Uventet fejl: {str(e)}")
    
    def _handle_notes_update_success(self):
        """Håndter succesfuld note opdatering"""
        self.refresh_notes_display()
        self.update_status("✅ AI noter opdateret!")
        self.add_to_chat("System", "🧠 AI noter om dig er opdateret baseret på samtalen!", "system")
    
    def _handle_notes_update_error(self, error):
        """Håndter note opdatering fejl"""
        self.update_status("❌ Fejl ved note opdatering")
        print(f"Note opdatering fejl: {error}")
    
    def refresh_notes_display(self):
        """Opdater noter display"""
        # Tjek om GUI er klar
        if not hasattr(self, 'notes_display'):
            return
            
        self.notes_display.config(state=tk.NORMAL)
        self.notes_display.delete("1.0", tk.END)
        
        if any(self.user_notes.values()):
            notes_text = ""
            if self.user_notes.get("personality"):
                notes_text += f"👤 Personlighed: {self.user_notes['personality']}\n\n"
            if self.user_notes.get("preferences"):
                notes_text += f"❤️ Præferencer: {self.user_notes['preferences']}\n\n"
            if self.user_notes.get("interests"):
                notes_text += f"🎯 Interesser: {self.user_notes['interests']}\n\n"
            if self.user_notes.get("communication_style"):
                notes_text += f"💬 Kommunikation: {self.user_notes['communication_style']}\n\n"
            if self.user_notes.get("technical_level"):
                notes_text += f"🔧 Teknisk niveau: {self.user_notes['technical_level']}\n\n"
            if self.user_notes.get("last_updated"):
                notes_text += f"🕒 Opdateret: {self.user_notes['last_updated']}"
            
            self.notes_display.insert("1.0", notes_text)
        else:
            self.notes_display.insert("1.0", "Ingen noter endnu. Chat med AI'en og klik 'Opdater noter' for at få personlige noter!")
        
        self.notes_display.config(state=tk.DISABLED)
    
    def show_full_notes(self):
        """Vis alle noter i nyt vindue"""
        notes_window = tk.Toplevel(self.root)
        notes_window.title("🧠 Komplette AI Noter")
        notes_window.geometry("600x400")
        
        notes_text = scrolledtext.ScrolledText(notes_window, wrap=tk.WORD, font=("Arial", 11))
        notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        full_notes = json.dumps(self.user_notes, ensure_ascii=False, indent=2)
        notes_text.insert("1.0", full_notes)
        notes_text.config(state=tk.DISABLED)
    
    # Filhåndtering
    def load_sessions(self):
        """Load sessions fra fil"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'rb') as f:
                    self.sessions = pickle.load(f)
        except:
            self.sessions = {}
    
    def save_sessions(self):
        """Gem sessions til fil"""
        try:
            with open(self.sessions_file, 'wb') as f:
                pickle.dump(self.sessions, f)
        except Exception as e:
            print(f"Fejl ved gemning af sessions: {e}")
    
    # Eksisterende metoder (opdateret for session support)
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
            
            # Tilføj bruger noter til system prompt hvis de eksisterer
            enhanced_system_prompt = self.system_prompt["content"]
            if any(self.user_notes.values()):
                notes_summary = f"\n\nVigtige noter om brugeren:\n"
                if self.user_notes.get("personality"):
                    notes_summary += f"- Personlighed: {self.user_notes['personality']}\n"
                if self.user_notes.get("preferences"):
                    notes_summary += f"- Præferencer: {self.user_notes['preferences']}\n"
                if self.user_notes.get("communication_style"):
                    notes_summary += f"- Kommunikationsstil: {self.user_notes['communication_style']}\n"
                if self.user_notes.get("technical_level"):
                    notes_summary += f"- Teknisk niveau: {self.user_notes['technical_level']}\n"
                enhanced_system_prompt += notes_summary
            
            # Tilføj til historie
            self.conversation_history.append({"role": "user", "content": prompt})
            
            # Begræns historik og tilføj enhanced system prompt
            recent_messages = self.conversation_history[-10:]
            messages = [{"role": "system", "content": enhanced_system_prompt}] + [msg for msg in recent_messages if msg["role"] != "system"]
            
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
        self.clear_chat_display()
        self.add_to_chat("System", "Chat ryddet. Start en ny samtale!", "system")
        
        # Opdater session
        if self.current_session_id and self.current_session_id in self.sessions:
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
    
    def run(self):
        """Start GUI"""
        try:
            # Gem sessions når programmet lukkes
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
    
    def on_closing(self):
        """Håndter lukning af program"""
        # Gem aktuel session
        if self.current_session_id and self.current_session_id in self.sessions:
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
        
        # Gem alle data
        self.save_sessions()
        self.save_user_notes()
        
        self.root.destroy()

def main():
    """Hovedfunktion"""
    print("🚀 Starter LLM Chat GUI med Sessions & AI Noter...")
    app = LLMChatGUI()
    app.run()

if __name__ == "__main__":
    main()