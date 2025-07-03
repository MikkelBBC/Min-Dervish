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
        
        # Konfigurerbare indstillinger
        self.timeout_seconds = 45  # Standard timeout
        self.timeout_enabled = True  # Om timeout er aktiveret
        
        # Bruger identifikation
        self.current_user = self.get_or_create_user()
        self.user_data_dir = f"user_data_{self.current_user}"
        self.ensure_user_directory()
        
        # Session management (per bruger)
        self.sessions = {}
        self.current_session_id = None
        self.sessions_file = os.path.join(self.user_data_dir, "chat_sessions.pkl")
        
        # AI Hukommelse system (automatisk og persistent)
        self.user_memory = {}  # Format: {memory_id: memory_data}
        self.memory_file = os.path.join(self.user_data_dir, "user_memory.json")
        self.auto_memory_threshold = 3  # Antal beskeder før automatisk memory-opdatering
        self.message_count = 0
        
        # Load eksisterende data
        self.load_sessions()
        self.load_user_memory()
        
        # System prompts
        self.danish_prompt = """Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise. 
        Du har adgang til information om brugeren som kan hjælpe dig med at give bedre og mere personlige svar."""
        
        self.english_prompt = """You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. 
        Keep responses concise and clear. You have access to user information that can help you provide better, more personalized responses."""
        
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
        
        # Top panel med sessions og hukommelse
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
        
        # AI Hukommelse panel (højre)
        memory_frame = ttk.LabelFrame(top_panel, text="🧠 AI Hukommelse (Permanent)", padding="5")
        memory_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Hukommelse controls
        memory_controls = ttk.Frame(memory_frame)
        memory_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(memory_controls, text="🔄 Opdater nu", command=self.force_update_memory, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(memory_controls, text="👁️ Vis alt", command=self.show_all_memory, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(memory_controls, text="🧹 Ryd", command=self.clear_memory, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(memory_controls, text="⚙️ Indstil", command=self.open_settings, width=8).pack(side=tk.LEFT)
        
        # Memory display
        self.memory_display = scrolledtext.ScrolledText(memory_frame, height=6, font=("Arial", 9), 
                                                       bg="#f9f9f9", fg="darkblue")
        self.memory_display.pack(fill=tk.BOTH, expand=True)
        
        # Auto-memory status
        self.auto_memory_label = ttk.Label(memory_frame, text="🤖 Auto-hukommelse: Aktiveret", 
                                          font=("Arial", 8, "italic"))
        self.auto_memory_label.pack(fill=tk.X, pady=(2, 0))
        
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
        
        # Auto-memory toggle
        self.auto_memory_var = tk.BooleanVar(value=True)
        self.auto_memory_checkbox = ttk.Checkbutton(
            controls_row, 
            text="🧠 Auto-hukommelse", 
            variable=self.auto_memory_var,
            command=self.toggle_auto_memory
        )
        self.auto_memory_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
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
        
        # Status og memory counter
        status_frame = ttk.Frame(controls_row)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = ttk.Label(status_frame, text="🟡 Starter...")
        self.status_label.pack(anchor=tk.E)
        
        self.note_counter_label = ttk.Label(status_frame, text="🧠 Minder: 0", 
                                           font=("Arial", 8, "italic"))
        self.note_counter_label.pack(anchor=tk.E)
        
        # Load data og opdater displays
        self.refresh_sessions_list()
        self.refresh_memory_display()
        self.update_memory_counter()
        
        # Tilføj velkomstbesked
        self.add_to_chat("System", f"Velkommen! Du er logget ind som bruger {self.current_user}.\nAI'en husker automatisk information om dig mellem samtaler.\nCtrl+Enter for at sende besked.", "system")
    
    # Indstillinger vindue
    def open_settings(self):
        """Åbn indstillinger vindue"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("⚙️ Indstillinger")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        
        # Timeout indstillinger
        timeout_frame = ttk.LabelFrame(settings_window, text="⏱️ Timeout Indstillinger", padding="10")
        timeout_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Timeout enabled checkbox
        self.timeout_enabled_var = tk.BooleanVar(value=self.timeout_enabled)
        ttk.Checkbutton(timeout_frame, text="Aktiver timeout", 
                       variable=self.timeout_enabled_var).pack(anchor=tk.W, pady=(0, 5))
        
        # Timeout slider
        ttk.Label(timeout_frame, text="Timeout sekunder:").pack(anchor=tk.W)
        timeout_frame_inner = ttk.Frame(timeout_frame)
        timeout_frame_inner.pack(fill=tk.X, pady=5)
        
        self.timeout_var = tk.IntVar(value=self.timeout_seconds)
        self.timeout_scale = tk.Scale(timeout_frame_inner, from_=10, to=120, 
                                     orient=tk.HORIZONTAL, variable=self.timeout_var)
        self.timeout_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.timeout_label = ttk.Label(timeout_frame_inner, text=f"{self.timeout_seconds}s")
        self.timeout_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Bind scale update
        self.timeout_scale.bind("<Motion>", self.update_timeout_label)
        
        # Auto-hukommelse indstillinger
        memory_frame = ttk.LabelFrame(settings_window, text="🧠 Hukommelse Indstillinger", padding="10")
        memory_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(memory_frame, text="Opdater hukommelse hver X besked:").pack(anchor=tk.W)
        memory_threshold_frame = ttk.Frame(memory_frame)
        memory_threshold_frame.pack(fill=tk.X, pady=5)
        
        self.memory_threshold_var = tk.IntVar(value=self.auto_memory_threshold)
        self.memory_threshold_scale = tk.Scale(memory_threshold_frame, from_=1, to=10, 
                                              orient=tk.HORIZONTAL, variable=self.memory_threshold_var)
        self.memory_threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.memory_threshold_label = ttk.Label(memory_threshold_frame, text=f"{self.auto_memory_threshold}")
        self.memory_threshold_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.memory_threshold_scale.bind("<Motion>", self.update_memory_threshold_label)
        
        # Gem og luk knapper
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="💾 Gem", command=lambda: self.save_settings(settings_window)).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="❌ Annuller", command=settings_window.destroy).pack(side=tk.RIGHT)
    
    def update_timeout_label(self, event=None):
        """Opdater timeout label"""
        value = self.timeout_var.get()
        self.timeout_label.config(text=f"{value}s")
    
    def update_memory_threshold_label(self, event=None):
        """Opdater memory threshold label"""
        value = self.memory_threshold_var.get()
        self.memory_threshold_label.config(text=f"{value}")
    
    def save_settings(self, window):
        """Gem indstillinger"""
        self.timeout_enabled = self.timeout_enabled_var.get()
        self.timeout_seconds = self.timeout_var.get()
        self.auto_memory_threshold = self.memory_threshold_var.get()
        
        # Reset message counter
        self.message_count = 0
        
        window.destroy()
        self.add_to_chat("System", f"⚙️ Indstillinger gemt! Timeout: {'ON' if self.timeout_enabled else 'OFF'} ({self.timeout_seconds}s), Hukommelse: hver {self.auto_memory_threshold}. besked", "system")
    
    # AI Hukommelse System (Forenklet og automatisk)
    def load_user_memory(self):
        """Load bruger hukommelse fra fil"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.user_memory = json.load(f)
            else:
                self.user_memory = {}
        except Exception as e:
            print(f"Fejl ved loading af hukommelse: {e}")
            self.user_memory = {}
    
    def save_user_memory(self):
        """Gem bruger hukommelse til fil"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fejl ved gemning af hukommelse: {e}")
    
    def check_auto_memory_update(self):
        """Tjek om det er tid til automatisk hukommelse opdatering"""
        if not self.auto_memory_var.get():
            return
            
        self.message_count += 1
        
        # Vis at systemet tæller beskeder
        if hasattr(self, 'auto_memory_label'):
            self.auto_memory_label.config(text=f"🤖 Auto-hukommelse: {self.message_count}/{self.auto_memory_threshold}")
        
        if self.message_count >= self.auto_memory_threshold:
            self.message_count = 0
            self.auto_memory_label.config(text="🔄 Analyserer samtale...")
            threading.Thread(target=self._auto_update_memory, daemon=True).start()
    
    def _auto_update_memory(self):
        """Automatisk opdatering af hukommelse (baggrund)"""
        try:
            # Saml seneste beskeder til analyse
            recent_messages = []
            for msg in self.conversation_history[-4:]:  # Sidste 4 beskeder
                if msg["role"] in ["user", "assistant"]:
                    recent_messages.append(f"{msg['role']}: {msg['content']}")
            
            if len(recent_messages) < 2:
                return
            
            conversation_text = "\n".join(recent_messages)
            
            # Fokuseret prompt for at fange interessante information
            analysis_prompt = f"""Analyser denne samtale og find interessant information om brugeren som jeg skal huske.

SAMTALE:
{conversation_text}

Find ALLE interessante facts om personen - navn, hobbier, præferencer, job, familie, mål, problemer, etc.

Svar med JSON:
{{
    "memories": [
        {{"info": "konkret fact om personen", "importance": 1-10}}
    ]
}}

Kun vigtig information (importance 5+). Tom liste hvis intet interessant."""
            
            headers = {"Content-Type": "application/json"}
            data = {
                "messages": [{"role": "user", "content": analysis_prompt}],
                "temperature": 0.1,
                "max_tokens": 300,
                "stream": False
            }
            
            # Brug konfigurerbar timeout
            timeout = self.timeout_seconds if self.timeout_enabled else None
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=timeout)
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
                    memory_updates = json.loads(json_str)
                    
                    # Tilføj nye minder
                    new_count = 0
                    if "memories" in memory_updates:
                        for memory_data in memory_updates["memories"]:
                            importance = memory_data.get("importance", 0)
                            if importance >= 5:  # Kun vigtige minder
                                info = memory_data.get("info", "")
                                
                                if info and not self._memory_exists(info):
                                    memory_id = str(int(time.time() * 1000))
                                    self.user_memory[memory_id] = {
                                        "info": info,
                                        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "importance": importance
                                    }
                                    new_count += 1
                    
                    # Gem og opdater GUI hvis der er nye minder
                    if new_count > 0:
                        self.save_user_memory()
                        self.root.after(0, self._handle_auto_memory_success, new_count)
                    else:
                        # Vis at systemet kører, selvom ingen nye minder
                        self.root.after(0, lambda: self.auto_memory_label.config(text="🤖 Ingen nye minder denne gang"))
                        self.root.after(3000, lambda: self.auto_memory_label.config(text="🤖 Auto-hukommelse: Aktiveret"))
                    
            except json.JSONDecodeError as e:
                print(f"Auto-hukommelse JSON fejl: {e}")
                self.root.after(0, lambda: self.auto_memory_label.config(text="❌ Hukommelse JSON fejl"))
                
        except requests.exceptions.Timeout:
            print("Auto-hukommelse timeout")
            self.root.after(0, lambda: self.auto_memory_label.config(text="⏱️ Hukommelse timeout (juster i indstillinger)"))
            self.root.after(5000, lambda: self.auto_memory_label.config(text="🤖 Auto-hukommelse: Aktiveret"))
        except requests.exceptions.ConnectionError:
            print("Auto-hukommelse forbindelse fejl")
            self.root.after(0, lambda: self.auto_memory_label.config(text="❌ LLM ikke tilgængelig"))
        except Exception as e:
            print(f"Auto-hukommelse generel fejl: {e}")
            self.root.after(0, lambda: self.auto_memory_label.config(text="❌ Hukommelse fejl"))
    
    def _memory_exists(self, new_info):
        """Tjek om lignende hukommelse allerede eksisterer"""
        new_info_lower = new_info.lower()
        for memory_data in self.user_memory.values():
            existing_info = memory_data.get("info", "").lower()
            # Simpel check for overlap (kan forbedres)
            if len(new_info_lower) > 10 and new_info_lower in existing_info:
                return True
            if len(existing_info) > 10 and existing_info in new_info_lower:
                return True
        return False
    
    def _handle_auto_memory_success(self, new_count):
        """Håndter succesfuld auto-hukommelse opdatering"""
        self.refresh_memory_display()
        self.update_memory_counter()
        
        if new_count > 0:
            status_msg = f"✅ {new_count} nye minder!"
            self.auto_memory_label.config(text=status_msg)
            
            # Reset til normal status efter 3 sekunder
            self.root.after(3000, lambda: self.auto_memory_label.config(text="🤖 Auto-hukommelse: Aktiveret"))
    
    def force_update_memory(self):
        """Tving hukommelse opdatering nu"""
        if len(self.conversation_history) < 3:
            messagebox.showinfo("Info", "For få beskeder til at opdatere hukommelse. Chat lidt mere først!")
            return
        
        self.auto_memory_label.config(text="🔄 Opdaterer hukommelse...")
        threading.Thread(target=self._auto_update_memory, daemon=True).start()
    
    def refresh_memory_display(self):
        """Opdater hukommelse display"""
        if not hasattr(self, 'memory_display'):
            return
        
        self.memory_display.config(state=tk.NORMAL)
        self.memory_display.delete("1.0", tk.END)
        
        if self.user_memory:
            # Sorter efter vigtighed og dato
            sorted_memories = sorted(self.user_memory.items(), 
                                   key=lambda x: (x[1].get("importance", 0), x[1].get("created", "")), 
                                   reverse=True)
            
            for memory_id, memory_data in sorted_memories[:10]:  # Vis top 10
                info = memory_data.get("info", "")
                importance = memory_data.get("importance", 0)
                created = memory_data.get("created", "")
                
                stars = "⭐" * min(importance, 5)  # Max 5 stjerner visuel
                self.memory_display.insert(tk.END, f"• {info} {stars}\n")
                self.memory_display.insert(tk.END, f"  📅 {created}\n\n")
        else:
            self.memory_display.insert(tk.END, "Ingen minder endnu.\n\nChat med AI'en og den vil automatisk huske interessant information om dig!")
        
        self.memory_display.config(state=tk.DISABLED)
    
    def show_all_memory(self):
        """Vis alle minder i nyt vindue"""
        memory_window = tk.Toplevel(self.root)
        memory_window.title(f"🧠 Alle Minder - Bruger: {self.current_user}")
        memory_window.geometry("700x500")
        
        # Sorter efter vigtighed
        controls_frame = ttk.Frame(memory_window)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(controls_frame, text="Sorter efter:").pack(side=tk.LEFT, padx=(0, 5))
        
        sort_var = tk.StringVar(value="Vigtighed")
        sort_combo = ttk.Combobox(controls_frame, textvariable=sort_var, 
                                 values=["Vigtighed", "Dato (nyeste)", "Dato (ældste)"], 
                                 state="readonly", width=15)
        sort_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        text_widget = scrolledtext.ScrolledText(memory_window, wrap=tk.WORD, font=("Arial", 11))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def update_display():
            text_widget.config(state=tk.NORMAL)
            text_widget.delete("1.0", tk.END)
            
            if not self.user_memory:
                text_widget.insert(tk.END, "Ingen minder endnu.")
                text_widget.config(state=tk.DISABLED)
                return
            
            # Sorter baseret på valg
            sort_choice = sort_var.get()
            if sort_choice == "Vigtighed":
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("importance", 0), reverse=True)
            elif sort_choice == "Dato (nyeste)":
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("created", ""), reverse=True)
            else:  # Dato (ældste)
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("created", ""))
            
            for i, (memory_id, memory_data) in enumerate(sorted_memories, 1):
                info = memory_data.get("info", "")
                importance = memory_data.get("importance", 0)
                created = memory_data.get("created", "Ukendt")
                
                stars = "⭐" * importance
                text_widget.insert(tk.END, f"{i}. {info}\n")
                text_widget.insert(tk.END, f"   Vigtighed: {stars} ({importance}/10)\n")
                text_widget.insert(tk.END, f"   📅 Oprettet: {created}\n")
                text_widget.insert(tk.END, f"   🆔 ID: {memory_id}\n\n")
            
            text_widget.config(state=tk.DISABLED)
        
        sort_combo.bind('<<ComboboxSelected>>', lambda e: update_display())
        update_display()
    
    def clear_memory(self):
        """Ryd alle minder efter bekræftelse"""
        if messagebox.askyesno("Bekræft", "Slet ALLE minder? Dette kan ikke fortrydes!"):
            self.user_memory = {}
            self.save_user_memory()
            self.refresh_memory_display()
            self.update_memory_counter()
            self.add_to_chat("System", "🧹 Alle minder er slettet!", "system")
    
    def update_memory_counter(self):
        """Opdater memory tæller"""
        if hasattr(self, 'note_counter_label'):
            total_memories = len(self.user_memory)
            self.note_counter_label.config(text=f"🧠 Minder: {total_memories}")
    
    def toggle_auto_memory(self):
        """Toggle automatiske minder"""
        enabled = self.auto_memory_var.get()
        status = "Aktiveret" if enabled else "Deaktiveret"
        self.auto_memory_label.config(text=f"🤖 Auto-hukommelse: {status}")
        
        if enabled:
            self.add_to_chat("System", "🤖 Automatisk hukommelse aktiveret!", "system")
        else:
            self.add_to_chat("System", "🤖 Automatisk hukommelse deaktiveret.", "system")
    
    def get_memory_for_ai(self):
        """Få minder til AI system prompt"""
        if not self.user_memory:
            return ""
        
        memory_summary = "\n\nVigtig information om brugeren (brug til at give bedre svar):\n"
        
        # Få de mest vigtige minder
        sorted_memories = sorted(self.user_memory.items(), 
                               key=lambda x: x[1].get("importance", 0), reverse=True)
        
        for memory_id, memory_data in sorted_memories[:8]:  # Top 8 vigtigste minder
            info = memory_data.get("info", "")
            if info:
                memory_summary += f"- {info}\n"
        
        return memory_summary
    
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
            
            # Vis hvor mange minder AI'en allerede har
            memory_count = len(self.user_memory)
            if memory_count > 0:
                self.add_to_chat("System", f"Ny samtale '{session_name}' oprettet! AI'en husker allerede {memory_count} ting om dig.", "system")
            else:
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
            
            # Byg forbedret system prompt med AI minder
            enhanced_system_prompt = self.system_prompt["content"]
            memory_summary = self.get_memory_for_ai()
            if memory_summary:
                enhanced_system_prompt += memory_summary
            
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
            
            # Brug konfigurerbar timeout
            timeout = self.timeout_seconds if self.timeout_enabled else None
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            assistant_response = result['choices'][0]['message']['content']
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            # Opdater GUI i main thread
            self.root.after(0, self._handle_llm_response, assistant_response)
            
        except requests.exceptions.Timeout:
            timeout_msg = f"Timeout efter {self.timeout_seconds}s. Juster i indstillinger hvis nødvendigt."
            self.root.after(0, self._handle_llm_error, timeout_msg)
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
        
        # Tjek for automatisk hukommelse opdatering
        self.check_auto_memory_update()
        
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
        
        # Vis eksisterende minder når chat ryddes
        memory_count = len(self.user_memory)
        if memory_count > 0:
            self.add_to_chat("System", f"Chat ryddet. AI'en husker stadig {memory_count} ting om dig! Start en ny samtale.", "system")
        else:
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
        self.save_user_memory()
        
        self.root.destroy()

def main():
    """Hovedfunktion"""
    print("🚀 Starter Optimeret LLM Chat GUI...")
    print("✨ Nye funktioner:")
    print("  - Konfigurerbar timeout (10-120 sekunder)")
    print("  - Kan slå timeout helt fra")
    print("  - Automatisk AI hukommelse (ingen kategorier)")
    print("  - Permanent hukommelse på tværs af samtaler")
    print("  - Indstillinger menu (⚙️)")
    print("  - Bruger isolation (sikre samtaler)")
    app = LLMChatGUI()
    app.run()

if __name__ == "__main__":
    main()