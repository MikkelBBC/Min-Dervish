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
import hashlib
import getpass

class LLMChatGUI:
    def __init__(self, llm_url="http://localhost:1234/v1/chat/completions"):
        # LLM URL
        self.llm_url = llm_url
        
        # Bruger identifikation
        self.current_user = self.get_or_create_user()
        self.user_data_dir = f"user_data_{self.current_user}"
        self.ensure_user_directory()
        
        # Session management (per bruger)
        self.sessions = {}
        self.current_session_id = None
        self.sessions_file = os.path.join(self.user_data_dir, "chat_sessions.pkl")
        
        # AI Noter system (løbende og automatisk)
        self.ai_notes = {}  # Format: {kategori: {note_id: note_data}}
        self.notes_file = os.path.join(self.user_data_dir, "ai_notes.json")
        self.auto_note_threshold = 3  # Antal beskeder før automatisk note-opdatering
        self.message_count = 0
        
        # Load eksisterende data
        self.load_sessions()
        self.load_ai_notes()
        
        # System prompts
        self.danish_prompt = """Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise. 
        Du har adgang til noter om brugeren som kan hjælpe dig med at give bedre og mere personlige svar."""
        
        self.english_prompt = """You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. 
        Keep responses concise and clear. You have access to user notes that can help you provide better, more personalized responses."""
        
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
        
        # GUI setup
        self.setup_gui()
        
        # Start med ny session
        self.create_new_session()
        
        self.init_tts()
        self.init_microphone()
        
        # Test forbindelse ved start
        self.test_connection()
    
    def get_or_create_user(self):
        """Få eller opret bruger ID baseret på system"""
        # Kombiner username og computer navn for unik ID
        username = getpass.getuser()
        computer_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
        user_string = f"{username}@{computer_name}"
        
        # Lav hash for privatliv
        user_hash = hashlib.md5(user_string.encode()).hexdigest()[:8]
        return user_hash
    
    def ensure_user_directory(self):
        """Sikr at bruger directory eksisterer"""
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
    
    def setup_gui(self):
        """Opret GUI vindue"""
        self.root = tk.Tk()
        self.root.title(f"🤖 LLM Chat - Bruger: {self.current_user}")
        self.root.geometry("1200x800")
        self.root.configure(bg="#f0f0f0")
        
        # Hovedframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top panel med sessions og AI noter
        top_panel = ttk.Frame(main_frame)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        
        # Sessions panel (venstre)
        sessions_frame = ttk.LabelFrame(top_panel, text="📁 Mine Samtaler", padding="5")
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
        
        # AI Noter panel (højre) - Nu med kategorier
        notes_frame = ttk.LabelFrame(top_panel, text="🧠 AI Noter (Automatiske)", padding="5")
        notes_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Noter controls
        notes_controls = ttk.Frame(notes_frame)
        notes_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(notes_controls, text="🔄 Opdater nu", command=self.force_update_notes, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(notes_controls, text="👁️ Alle noter", command=self.show_all_notes, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(notes_controls, text="🧹 Ryd noter", command=self.clear_notes, width=10).pack(side=tk.LEFT)
        
        # Note kategorier dropdown
        kategori_frame = ttk.Frame(notes_frame)
        kategori_frame.pack(fill=tk.X, pady=(5, 5))
        
        ttk.Label(kategori_frame, text="📂 Kategori:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.kategori_var = tk.StringVar(value="Alle")
        self.kategori_combo = ttk.Combobox(kategori_frame, textvariable=self.kategori_var, width=15, state="readonly")
        self.kategori_combo['values'] = ['Alle', 'Personlighed', 'Interesser', 'Præferencer', 'Færdigheder', 'Mål', 'Andre']
        self.kategori_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.kategori_combo.bind('<<ComboboxSelected>>', self.refresh_notes_display)
        
        # Note display
        self.notes_display = scrolledtext.ScrolledText(notes_frame, height=6, font=("Arial", 9), 
                                                      bg="#f9f9f9", fg="darkblue")
        self.notes_display.pack(fill=tk.BOTH, expand=True)
        
        # Auto-note status
        self.auto_note_label = ttk.Label(notes_frame, text="🤖 Auto-noter: Aktiveret", 
                                        font=("Arial", 8, "italic"))
        self.auto_note_label.pack(fill=tk.X, pady=(2, 0))
        
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
        
        # Auto-noter toggle
        self.auto_notes_var = tk.BooleanVar(value=True)
        self.auto_notes_checkbox = ttk.Checkbutton(
            controls_row, 
            text="🤖 Auto-noter", 
            variable=self.auto_notes_var,
            command=self.toggle_auto_notes
        )
        self.auto_notes_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
        # Clear chat
        ttk.Button(
            controls_row, 
            text="🧹 Ryd chat", 
            command=self.clear_chat
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Session navn og bruger info
        info_frame = ttk.Frame(controls_row)
        info_frame.pack(side=tk.LEFT, padx=(20, 10))
        
        self.session_name_label = ttk.Label(info_frame, text="📝 Aktuel: Ny samtale", 
                                           font=("Arial", 10, "italic"))
        self.session_name_label.pack(anchor=tk.W)
        
        self.user_label = ttk.Label(info_frame, text=f"👤 Bruger: {self.current_user}", 
                                   font=("Arial", 8, "italic"))
        self.user_label.pack(anchor=tk.W)
        
        # Status og note counter
        status_frame = ttk.Frame(controls_row)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = ttk.Label(status_frame, text="🟡 Starter...")
        self.status_label.pack(anchor=tk.E)
        
        self.note_counter_label = ttk.Label(status_frame, text="📝 Noter: 0", 
                                           font=("Arial", 8, "italic"))
        self.note_counter_label.pack(anchor=tk.E)
        
        # Load data og opdater displays
        self.refresh_sessions_list()
        self.refresh_notes_display()
        self.update_note_counter()
        
        # Tilføj velkomstbesked
        self.add_to_chat("System", f"Velkommen! Du er logget ind som bruger {self.current_user}.\nAI'en tager automatiske noter om dig og husker mellem samtaler.\nCtrl+Enter for at sende besked.", "system")
    
    # AI Noter System (Forbedret og automatisk)
    def load_ai_notes(self):
        """Load AI noter fra fil"""
        try:
            if os.path.exists(self.notes_file):
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    self.ai_notes = json.load(f)
            else:
                self.ai_notes = {
                    "Personlighed": {},
                    "Interesser": {},
                    "Præferencer": {},
                    "Færdigheder": {},
                    "Mål": {},
                    "Andre": {}
                }
        except Exception as e:
            print(f"Fejl ved loading af AI noter: {e}")
            self.ai_notes = {
                "Personlighed": {},
                "Interesser": {},
                "Præferencer": {},
                "Færdigheder": {},
                "Mål": {},
                "Andre": {}
            }
    
    def save_ai_notes(self):
        """Gem AI noter til fil"""
        try:
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump(self.ai_notes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fejl ved gemning af AI noter: {e}")
    
    def check_auto_note_update(self):
        """Tjek om det er tid til automatisk note opdatering"""
        if not self.auto_notes_var.get():
            return
            
        self.message_count += 1
        
        if self.message_count >= self.auto_note_threshold:
            self.message_count = 0
            threading.Thread(target=self._auto_update_notes, daemon=True).start()
    
    def _auto_update_notes(self):
        """Automatisk opdatering af noter (baggrund)"""
        try:
            # Saml seneste beskeder til analyse
            recent_messages = []
            for msg in self.conversation_history[-6:]:  # Sidste 6 beskeder
                if msg["role"] in ["user", "assistant"]:
                    recent_messages.append(f"{msg['role']}: {msg['content']}")
            
            if len(recent_messages) < 2:
                return
            
            conversation_text = "\n".join(recent_messages)
            
            analysis_prompt = f"""Analyser denne seneste samtale og udtræk nye indsigter om brugeren.

EKSISTERENDE NOTER:
{json.dumps(self.ai_notes, ensure_ascii=False, indent=1)}

SENESTE SAMTALE:
{conversation_text}

Svar med PRÆCIS dette JSON format - ingen ekstra tekst:
{{
    "nye_noter": [
        {{
            "kategori": "Personlighed|Interesser|Præferencer|Færdigheder|Mål|Andre",
            "note": "kort specifik note",
            "relevans": 1-10
        }}
    ],
    "opdaterede_noter": [
        {{
            "kategori": "kategori_navn",
            "note_id": "eksisterende_note_id",
            "ny_note": "opdateret note tekst"
        }}
    ]
}}

Kun tilføj noter hvis der er nye, relevante indsigter. Tom liste er OK."""
            
            headers = {"Content-Type": "application/json"}
            data = {
                "messages": [{"role": "user", "content": analysis_prompt}],
                "temperature": 0.2,
                "max_tokens": 500,
                "stream": False
            }
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            ai_response = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON respons
            try:
                ai_response = ai_response.replace('```json', '').replace('```', '').strip()
                start = ai_response.find('{')
                end = ai_response.rfind('}') + 1
                
                if start >= 0 and end > start:
                    json_str = ai_response[start:end]
                    note_updates = json.loads(json_str)
                    
                    # Behandl nye noter
                    new_count = 0
                    if "nye_noter" in note_updates:
                        for note_data in note_updates["nye_noter"]:
                            if note_data.get("relevans", 0) >= 5:  # Kun relevante noter
                                kategori = note_data.get("kategori", "Andre")
                                note_text = note_data.get("note", "")
                                
                                if kategori in self.ai_notes and note_text:
                                    note_id = str(int(time.time() * 1000))  # Timestamp som ID
                                    self.ai_notes[kategori][note_id] = {
                                        "note": note_text,
                                        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "relevans": note_data.get("relevans", 5)
                                    }
                                    new_count += 1
                    
                    # Behandl opdateringer
                    update_count = 0
                    if "opdaterede_noter" in note_updates:
                        for update_data in note_updates["opdaterede_noter"]:
                            kategori = update_data.get("kategori")
                            note_id = update_data.get("note_id")
                            ny_note = update_data.get("ny_note")
                            
                            if (kategori in self.ai_notes and 
                                note_id in self.ai_notes[kategori] and 
                                ny_note):
                                self.ai_notes[kategori][note_id]["note"] = ny_note
                                self.ai_notes[kategori][note_id]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                update_count += 1
                    
                    # Gem og opdater GUI hvis der er ændringer
                    if new_count > 0 or update_count > 0:
                        self.save_ai_notes()
                        self.root.after(0, self._handle_auto_notes_success, new_count, update_count)
                    
            except json.JSONDecodeError as e:
                print(f"Auto-noter JSON fejl: {e}")
                
        except Exception as e:
            print(f"Auto-noter fejl: {e}")
    
    def _handle_auto_notes_success(self, new_count, update_count):
        """Håndter succesfuld auto-note opdatering"""
        self.refresh_notes_display()
        self.update_note_counter()
        
        if new_count > 0 or update_count > 0:
            status_msg = f"🤖 {new_count} nye noter"
            if update_count > 0:
                status_msg += f", {update_count} opdateret"
            self.auto_note_label.config(text=status_msg)
            
            # Reset til normal status efter 3 sekunder
            self.root.after(3000, lambda: self.auto_note_label.config(text="🤖 Auto-noter: Aktiveret"))
    
    def force_update_notes(self):
        """Tving note opdatering nu"""
        if len(self.conversation_history) < 3:
            messagebox.showinfo("Info", "For få beskeder til at opdatere noter. Chat lidt mere først!")
            return
        
        self.auto_note_label.config(text="🔄 Opdaterer noter...")
        threading.Thread(target=self._auto_update_notes, daemon=True).start()
    
    def refresh_notes_display(self, event=None):
        """Opdater noter display baseret på valgt kategori"""
        if not hasattr(self, 'notes_display'):
            return
        
        self.notes_display.config(state=tk.NORMAL)
        self.notes_display.delete("1.0", tk.END)
        
        kategori = self.kategori_var.get()
        
        if kategori == "Alle":
            # Vis alle kategorier
            for kat_navn, noter in self.ai_notes.items():
                if noter:  # Kun hvis der er noter i kategorien
                    self.notes_display.insert(tk.END, f"📂 {kat_navn}\n", f"kategori_{kat_navn}")
                    for note_id, note_data in sorted(noter.items(), 
                                                   key=lambda x: x[1].get("created", ""), reverse=True)[:3]:  # Max 3 per kategori
                        relevans = "⭐" * note_data.get("relevans", 1)
                        self.notes_display.insert(tk.END, f"  • {note_data['note']} {relevans}\n")
                    self.notes_display.insert(tk.END, "\n")
        else:
            # Vis specifik kategori
            if kategori in self.ai_notes and self.ai_notes[kategori]:
                self.notes_display.insert(tk.END, f"📂 {kategori}\n\n", f"kategori_{kategori}")
                for note_id, note_data in sorted(self.ai_notes[kategori].items(), 
                                               key=lambda x: x[1].get("created", ""), reverse=True):
                    created = note_data.get("created", "Ukendt")
                    relevans = "⭐" * note_data.get("relevans", 1)
                    self.notes_display.insert(tk.END, f"• {note_data['note']} {relevans}\n")
                    self.notes_display.insert(tk.END, f"  📅 {created}\n\n")
            else:
                self.notes_display.insert(tk.END, f"Ingen noter i '{kategori}' endnu.\n\nChat med AI'en og den vil automatisk tilføje noter!")
        
        # Styling
        for kat in self.ai_notes.keys():
            self.notes_display.tag_config(f"kategori_{kat}", foreground="darkblue", font=("Arial", 10, "bold"))
        
        self.notes_display.config(state=tk.DISABLED)
    
    def show_all_notes(self):
        """Vis alle noter i nyt vindue"""
        notes_window = tk.Toplevel(self.root)
        notes_window.title(f"🧠 Alle AI Noter - Bruger: {self.current_user}")
        notes_window.geometry("800x600")
        
        # Notebook for kategorier
        notebook = ttk.Notebook(notes_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for kategori, noter in self.ai_notes.items():
            if noter:  # Kun kategorier med noter
                frame = ttk.Frame(notebook)
                notebook.add(frame, text=f"{kategori} ({len(noter)})")
                
                text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Arial", 11))
                text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                for note_id, note_data in sorted(noter.items(), 
                                               key=lambda x: x[1].get("created", ""), reverse=True):
                    created = note_data.get("created", "Ukendt")
                    relevans = "⭐" * note_data.get("relevans", 1)
                    text_widget.insert(tk.END, f"• {note_data['note']} {relevans}\n")
                    text_widget.insert(tk.END, f"  📅 Oprettet: {created}\n")
                    if "updated" in note_data:
                        text_widget.insert(tk.END, f"  🔄 Opdateret: {note_data['updated']}\n")
                    text_widget.insert(tk.END, "\n")
                
                text_widget.config(state=tk.DISABLED)
    
    def clear_notes(self):
        """Ryd alle AI noter efter bekræftelse"""
        if messagebox.askyesno("Bekræft", "Slet ALLE AI noter? Dette kan ikke fortrydes!"):
            self.ai_notes = {
                "Personlighed": {},
                "Interesser": {},
                "Præferencer": {},
                "Færdigheder": {},
                "Mål": {},
                "Andre": {}
            }
            self.save_ai_notes()
            self.refresh_notes_display()
            self.update_note_counter()
            self.add_to_chat("System", "🧹 Alle AI noter er slettet!", "system")
    
    def update_note_counter(self):
        """Opdater note tæller"""
        if hasattr(self, 'note_counter_label'):
            total_notes = sum(len(noter) for noter in self.ai_notes.values())
            self.note_counter_label.config(text=f"📝 Noter: {total_notes}")
    
    def toggle_auto_notes(self):
        """Toggle automatiske noter"""
        enabled = self.auto_notes_var.get()
        status = "Aktiveret" if enabled else "Deaktiveret"
        self.auto_note_label.config(text=f"🤖 Auto-noter: {status}")
        
        if enabled:
            self.add_to_chat("System", "🤖 Automatiske noter aktiveret!", "system")
        else:
            self.add_to_chat("System", "🤖 Automatiske noter deaktiveret.", "system")
    
    def get_notes_for_ai(self):
        """Få noter til AI system prompt"""
        if not any(self.ai_notes.values()):
            return ""
        
        notes_summary = "\n\nVigtige noter om brugeren (brug til at give bedre svar):\n"
        
        for kategori, noter in self.ai_notes.items():
            if noter:
                # Få de mest relevante noter (højeste relevans score)
                top_notes = sorted(noter.items(), 
                                 key=lambda x: x[1].get("relevans", 0), reverse=True)[:2]
                if top_notes:
                    notes_summary += f"\n{kategori}:\n"
                    for note_id, note_data in top_notes:
                        notes_summary += f"  - {note_data['note']}\n"
        
        return notes_summary
    
    # Session Management (forbedret med bruger isolation)
    def create_new_session(self):
        """Opret ny session"""
        if not hasattr(self, 'sessions_listbox'):
            session_name = f"Samtale {len(self.sessions) + 1}"
        else:
            session_name = simpledialog.askstring("Ny samtale", "Navn på samtale:", 
                                                 initialvalue=f"Samtale {len(self.sessions) + 1}")
            if not session_name:
                return
        
        session_id = f"{self.current_user}_{int(time.time())}"  # Bruger-specifik ID
        self.sessions[session_id] = {
            "name": session_name,
            "history": [self.system_prompt.copy()],
            "created": datetime.now(),
            "user": self.current_user  # Sikr bruger tilhørighed
        }
        
        self.current_session_id = session_id
        self.conversation_history = self.sessions[session_id]["history"]
        self.message_count = 0  # Reset message counter
        
        if hasattr(self, 'sessions_listbox'):
            self.refresh_sessions_list()
            self.clear_chat_display()
            self.update_session_label()
            self.add_to_chat("System", f"Ny samtale '{session_name}' oprettet!", "system")
    
    def load_sessions(self):
        """Load kun denne brugers sessions"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'rb') as f:
                    all_sessions = pickle.load(f)
                    # Filtrer kun denne brugers sessions
                    self.sessions = {k: v for k, v in all_sessions.items() 
                                   if v.get("user") == self.current_user}
            else:
                self.sessions = {}
        except:
            self.sessions = {}
    
    def load_selected_session(self, event=None):
        """Load valgt session (kun hvis den tilhører brugeren)"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        # Sikr at sessionen tilhører denne bruger
        if (session_id in self.sessions and 
            self.sessions[session_id].get("user") == self.current_user):
            self.current_session_id = session_id
            self.conversation_history = self.sessions[session_id]["history"]
            self.refresh_chat_from_history()
            self.update_session_label()
            self.message_count = 0  # Reset counter for loaded session
        else:
            messagebox.showerror("Adgang nægtet", "Du har ikke adgang til denne samtale!")
    
    def save_current_session(self):
        """Gem aktuel session"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.current_user):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
            self.save_sessions()
            self.add_to_chat("System", "Samtale gemt! 💾", "system")
        else:
            messagebox.showwarning("Advarsel", "Ingen valid samtale at gemme")
    
    def delete_session(self):
        """Slet valgt session (kun hvis den tilhører brugeren)"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Vælg en samtale at slette")
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        # Sikr at sessionen tilhører denne bruger
        if (session_id in self.sessions and 
            self.sessions[session_id].get("user") == self.current_user):
            if messagebox.askyesno("Bekræft", f"Slet samtale '{self.sessions[session_id]['name']}'?"):
                del self.sessions[session_id]
                if self.current_session_id == session_id:
                    self.create_new_session()
                self.refresh_sessions_list()
                self.save_sessions()
        else:
            messagebox.showerror("Adgang nægtet", "Du kan ikke slette denne samtale!")
    
    def save_sessions(self):
        """Gem sessions til fil (med bruger data)"""
        try:
            # Load eksisterende sessions fra andre brugere
            all_sessions = {}
            if os.path.exists(self.sessions_file):
                try:
                    with open(self.sessions_file, 'rb') as f:
                        all_sessions = pickle.load(f)
                except:
                    pass
            
            # Opdater med denne brugers sessions
            all_sessions.update(self.sessions)
            
            # Gem alt
            with open(self.sessions_file, 'wb') as f:
                pickle.dump(all_sessions, f)
        except Exception as e:
            print(f"Fejl ved gemning af sessions: {e}")
    
    def refresh_sessions_list(self):
        """Opdater sessions liste (kun denne brugers)"""
        if not hasattr(self, 'sessions_listbox'):
            return
            
        self.sessions_listbox.delete(0, tk.END)
        
        # Filtrer og sorter kun denne brugers sessions
        user_sessions = {k: v for k, v in self.sessions.items() 
                        if v.get("user") == self.current_user}
        
        for session_id, session_data in sorted(user_sessions.items(), 
                                              key=lambda x: x[1]["created"], reverse=True):
            created_str = session_data["created"].strftime("%d/%m %H:%M")
            msg_count = len([msg for msg in session_data["history"] if msg["role"] == "user"])
            display_text = f"{session_id} - {session_data['name']} ({msg_count} beskeder, {created_str})"
            self.sessions_listbox.insert(0, display_text)
    
    def update_session_label(self):
        """Opdater session label"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions):
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
    
    # TTS og Speech Recognition
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
            
            # Byg forbedret system prompt med AI noter
            enhanced_system_prompt = self.system_prompt["content"]
            notes_summary = self.get_notes_for_ai()
            if notes_summary:
                enhanced_system_prompt += notes_summary
            
            # Tilføj til historie
            self.conversation_history.append({"role": "user", "content": prompt})
            
            # Begræns historik og tilføj enhanced system prompt
            recent_messages = self.conversation_history[-12:]  # Mere historie for bedre kontekst
            messages = [{"role": "system", "content": enhanced_system_prompt}] + [msg for msg in recent_messages if msg["role"] != "system"]
            
            data = {
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 400,
                "stream": False
            }
            
            self.update_status("🤖 Tænker...")
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=35)
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
        
        # Tjek for automatisk note opdatering
        self.check_auto_note_update()
        
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
        self.conversation_history = [self.system_prompt.copy()]
        self.clear_chat_display()
        self.message_count = 0  # Reset message counter
        self.add_to_chat("System", "Chat ryddet. Start en ny samtale!", "system")
        
        # Opdater session
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.current_user):
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
        # Gem aktuel session (kun hvis den tilhører brugeren)
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.current_user):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
        
        # Gem alle data
        self.save_sessions()
        self.save_ai_notes()
        
        self.root.destroy()

def main():
    """Hovedfunktion"""
    print("🚀 Starter Optimeret LLM Chat GUI...")
    print("✨ Nye funktioner:")
    print("  - Automatiske AI noter (løbende)")
    print("  - Bruger isolation (ingen delte samtaler)")
    print("  - Forbedret note system med kategorier")
    print("  - Bedre sikkerhed og performance")
    app = LLMChatGUI()
    app.run()

if __name__ == "__main__":
    main()