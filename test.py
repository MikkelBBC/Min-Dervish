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
import re
from bs4 import BeautifulSoup
import queue

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
        
        # AI Hukommelse system (forbedret)
        self.user_memory = {}  # Format: {memory_id: memory_data}
        self.memory_file = os.path.join(self.user_data_dir, "user_memory.json")
        self.auto_memory_threshold = 3  # Antal beskeder før automatisk memory-opdatering
        self.message_count = 0
        self.auto_memory_job = None
        
        # Opskrift søgning
        self.recipe_search_queue = queue.Queue()
        self.recipes_data = []
        
        # Load eksisterende data
        self.load_sessions()
        self.load_user_memory()
        
        # System prompts
        self.danish_prompt = """Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise. 
        Du har adgang til information om brugeren som kan hjælpe dig med at give bedre og mere personlige svar.
        Når brugeren beder om opskrifter, så giv altid mindst én konkret opskrift med ingredienser og fremgangsmåde."""
        
        self.english_prompt = """You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. 
        Keep responses concise and clear. You have access to user information that can help you provide better, more personalized responses.
        When the user asks for recipes, always provide at least one specific recipe with ingredients and instructions."""
        
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
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        
        # GUI setup
        self.setup_gui()
        
        # Start med ny session
        self.create_new_session()
        
        self.init_tts()
        self.init_microphone()
        
        # Start background threads
        self.start_tts_worker()
        self.check_recipe_queue()
        
        # Test forbindelse ved start
        self.test_connection()
    
    def get_or_create_user(self):
        """Få eller opret bruger ID baseret på system"""
        username = getpass.getuser()
        computer_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
        user_string = f"{username}@{computer_name}"
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
        self.root.geometry("1200x900")
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
        
        # Opskrift søgning område
        recipe_frame = ttk.LabelFrame(main_frame, text="🍳 Opskrift Søgning", padding="5")
        recipe_frame.pack(fill=tk.X, pady=(0, 10))
        
        recipe_controls = ttk.Frame(recipe_frame)
        recipe_controls.pack(fill=tk.X)
        
        ttk.Label(recipe_controls, text="Søg:").pack(side=tk.LEFT, padx=(0, 5))
        self.recipe_entry = ttk.Entry(recipe_controls, width=30)
        self.recipe_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.recipe_entry.bind('<Return>', lambda e: self.search_recipes())
        
        ttk.Button(recipe_controls, text="🔍 Søg Opskrifter", command=self.search_recipes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(recipe_controls, text="🔊 Læs Opskrift", command=self.read_selected_recipe).pack(side=tk.LEFT)
        
        # Progress bar for søgning
        self.search_progress = ttk.Progressbar(recipe_frame, mode='indeterminate')
        self.search_progress.pack(fill=tk.X, pady=(5, 0))
        
        # Resultat listbox
        self.recipe_listbox = tk.Listbox(recipe_frame, height=3, font=("Arial", 10))
        self.recipe_listbox.pack(fill=tk.X, pady=(5, 0))
        
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
    
    # Forbedret indstillinger vindue
    def open_settings(self):
        """Åbn indstillinger vindue"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("⚙️ Indstillinger")
        settings_window.geometry("400x400")
        settings_window.resizable(False, False)
        
        # Gem nuværende værdier
        self.temp_timeout_enabled = tk.BooleanVar(value=self.timeout_enabled)
        self.temp_timeout_seconds = tk.IntVar(value=self.timeout_seconds)
        self.temp_auto_memory_threshold = tk.IntVar(value=self.auto_memory_threshold)
        
        # Timeout indstillinger
        timeout_frame = ttk.LabelFrame(settings_window, text="⏱️ Timeout Indstillinger", padding="10")
        timeout_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Timeout enabled checkbox
        ttk.Checkbutton(timeout_frame, text="Aktiver timeout", 
                       variable=self.temp_timeout_enabled).pack(anchor=tk.W, pady=(0, 5))
        
        # Timeout slider
        ttk.Label(timeout_frame, text="Timeout sekunder:").pack(anchor=tk.W)
        timeout_frame_inner = ttk.Frame(timeout_frame)
        timeout_frame_inner.pack(fill=tk.X, pady=5)
        
        self.timeout_scale = tk.Scale(timeout_frame_inner, from_=10, to=120, 
                                     orient=tk.HORIZONTAL, variable=self.temp_timeout_seconds)
        self.timeout_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.timeout_label = ttk.Label(timeout_frame_inner, text=f"{self.temp_timeout_seconds.get()}s")
        self.timeout_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Bind scale update
        self.timeout_scale.bind("<Motion>", lambda e: self.timeout_label.config(text=f"{self.temp_timeout_seconds.get()}s"))
        
        # Auto-hukommelse indstillinger
        memory_frame = ttk.LabelFrame(settings_window, text="🧠 Hukommelse Indstillinger", padding="10")
        memory_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(memory_frame, text="Opdater hukommelse hver X besked:").pack(anchor=tk.W)
        memory_threshold_frame = ttk.Frame(memory_frame)
        memory_threshold_frame.pack(fill=tk.X, pady=5)
        
        self.memory_threshold_scale = tk.Scale(memory_threshold_frame, from_=1, to=10, 
                                              orient=tk.HORIZONTAL, variable=self.temp_auto_memory_threshold)
        self.memory_threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.memory_threshold_label = ttk.Label(memory_threshold_frame, text=f"{self.temp_auto_memory_threshold.get()}")
        self.memory_threshold_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.memory_threshold_scale.bind("<Motion>", lambda e: self.memory_threshold_label.config(text=f"{self.temp_auto_memory_threshold.get()}"))
        
        # Gem og luk knapper
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="💾 Gem", command=lambda: self.save_settings(settings_window)).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="❌ Annuller", command=settings_window.destroy).pack(side=tk.RIGHT)
    
    def save_settings(self, window):
        """Gem indstillinger (nu virker det!)"""
        # Gem værdierne
        self.timeout_enabled = self.temp_timeout_enabled.get()
        self.timeout_seconds = self.temp_timeout_seconds.get()
        self.auto_memory_threshold = self.temp_auto_memory_threshold.get()
        
        # Reset message counter
        self.message_count = 0
        
        # Gem til fil
        settings = {
            'timeout_enabled': self.timeout_enabled,
            'timeout_seconds': self.timeout_seconds,
            'auto_memory_threshold': self.auto_memory_threshold
        }
        
        settings_file = os.path.join(self.user_data_dir, "settings.json")
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Fejl ved gemning af indstillinger: {e}")
        
        window.destroy()
        self.add_to_chat("System", f"⚙️ Indstillinger gemt! Timeout: {'ON' if self.timeout_enabled else 'OFF'} ({self.timeout_seconds}s), Hukommelse: hver {self.auto_memory_threshold}. besked", "system")
    
    # Forbedret AI Hukommelse System
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
        """Forbedret automatisk opdatering af hukommelse"""
        try:
            # Saml seneste beskeder til analyse
            recent_messages = []
            for msg in self.conversation_history[-6:]:  # Sidste 6 beskeder for bedre kontekst
                if msg["role"] in ["user", "assistant"]:
                    recent_messages.append(f"{msg['role']}: {msg['content']}")
            
            if len(recent_messages) < 2:
                return
            
            conversation_text = "\n".join(recent_messages)
            
            # Forbedret prompt for at fange personlig information
            analysis_prompt = f"""Analyser denne samtale og find AL personlig information om brugeren.

SAMTALE:
{conversation_text}

Find og returner i JSON format:
1. Navn (fx "Mikkel")
2. Alder (fx 21)
3. Lokation/by
4. Job/uddannelse
5. Interesser/hobbyer
6. Familie info
7. Præferencer (mad, aktiviteter, etc.)
8. Andre vigtige fakta

VIGTIGT: Returner KUN ren JSON, ingen anden tekst!

JSON struktur:
{{
    "memories": [
        {{"category": "navn", "info": "Mikkel", "importance": 10}},
        {{"category": "alder", "info": "21 år", "importance": 9}},
        {{"category": "andet", "info": "beskrivelse", "importance": 1-10}}
    ]
}}

Hvis ingen ny info, returner: {{"memories": []}}"""
            
            headers = {"Content-Type": "application/json"}
            data = {
                "messages": [{"role": "user", "content": analysis_prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
            
            # Brug konfigurerbar timeout
            timeout = self.timeout_seconds if self.timeout_enabled else None
            
            response = requests.post(self.llm_url, json=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            ai_response = result['choices'][0]['message']['content'].strip()
            
            # Forbedret JSON parsing
            memory_updates = self.parse_json_response(ai_response)
            
            if memory_updates and "memories" in memory_updates:
                new_count = 0
                for memory_data in memory_updates["memories"]:
                    if memory_data.get("info") and memory_data.get("importance", 0) >= 5:
                        memory_id = str(int(time.time() * 1000))
                        
                        # Check for duplikater
                        if not self._memory_exists(memory_data["info"]):
                            self.user_memory[memory_id] = {
                                "category": memory_data.get("category", "general"),
                                "info": memory_data["info"],
                                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "importance": memory_data.get("importance", 5)
                            }
                            new_count += 1
                
                if new_count > 0:
                    self.save_user_memory()
                    self.root.after(0, self._handle_auto_memory_success, new_count)
                else:
                    self.root.after(0, lambda: self.auto_memory_label.config(text="🤖 Ingen nye minder denne gang"))
                    self.root.after(3000, lambda: self.auto_memory_label.config(text="🤖 Auto-hukommelse: Aktiveret"))
                    
        except Exception as e:
            print(f"Auto-hukommelse fejl: {e}")
            self.root.after(0, lambda: self.auto_memory_label.config(text="❌ Hukommelse fejl"))
    
    def parse_json_response(self, response_text):
        """Robust JSON parsing med flere metoder"""
        # Metode 1: Direkte parsing
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Metode 2: Find JSON i tekst
        try:
            # Fjern markdown code blocks
            cleaned = response_text.replace('```json', '').replace('```', '').strip()
            
            # Find JSON mellem krølparenteser
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Metode 3: Manuel extraction som fallback
        try:
            memories = []
            
            # Søg efter navn
            name_patterns = [
                r'(?:jeg hedder|mit navn er|jeg er)\s+(\w+)',
                r'navn["\s:]+(\w+)',
                r'"name"[:\s]+"(\w+)"'
            ]
            for pattern in name_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    memories.append({
                        "category": "navn",
                        "info": match.group(1),
                        "importance": 10
                    })
                    break
            
            # Søg efter alder
            age_patterns = [
                r'(\d+)\s*år',
                r'alder["\s:]+(\d+)',
                r'"age"[:\s]+(\d+)'
            ]
            for pattern in age_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    memories.append({
                        "category": "alder",
                        "info": f"{match.group(1)} år",
                        "importance": 9
                    })
                    break
            
            if memories:
                return {"memories": memories}
        except:
            pass
        
        return None
    
    def _memory_exists(self, new_info):
        """Tjek om lignende hukommelse allerede eksisterer"""
        new_info_lower = new_info.lower()
        for memory_data in self.user_memory.values():
            existing_info = memory_data.get("info", "").lower()
            # Simpel check for overlap
            if len(new_info_lower) > 5 and new_info_lower in existing_info:
                return True
            if len(existing_info) > 5 and existing_info in new_info_lower:
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
            # Sorter efter vigtighed og kategori
            sorted_memories = sorted(self.user_memory.items(), 
                                   key=lambda x: (x[1].get("importance", 0), x[1].get("category", "")), 
                                   reverse=True)
            
            # Grupper efter kategori
            categories = {}
            for memory_id, memory_data in sorted_memories:
                category = memory_data.get("category", "andet")
                if category not in categories:
                    categories[category] = []
                categories[category].append(memory_data)
            
            # Vis grupperet
            for category, memories in categories.items():
                self.memory_display.insert(tk.END, f"📌 {category.upper()}:\n", "category")
                for memory in memories[:3]:  # Max 3 per kategori
                    info = memory.get("info", "")
                    importance = memory.get("importance", 0)
                    stars = "⭐" * min(importance // 2, 5)
                    self.memory_display.insert(tk.END, f"  • {info} {stars}\n")
                self.memory_display.insert(tk.END, "\n")
        else:
            self.memory_display.insert(tk.END, "Ingen minder endnu.\n\nChat med AI'en og den vil automatisk huske interessant information om dig!")
        
        # Styling
        self.memory_display.tag_config("category", foreground="darkblue", font=("Arial", 10, "bold"))
        self.memory_display.config(state=tk.DISABLED)
    
    def show_all_memory(self):
        """Vis alle minder i nyt vindue"""
        memory_window = tk.Toplevel(self.root)
        memory_window.title(f"🧠 Alle Minder - Bruger: {self.current_user}")
        memory_window.geometry("700x500")
        
        # Sorter og filter controls
        controls_frame = ttk.Frame(memory_window)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(controls_frame, text="Sorter efter:").pack(side=tk.LEFT, padx=(0, 5))
        
        sort_var = tk.StringVar(value="Vigtighed")
        sort_combo = ttk.Combobox(controls_frame, textvariable=sort_var, 
                                 values=["Vigtighed", "Kategori", "Dato (nyeste)", "Dato (ældste)"], 
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
            elif sort_choice == "Kategori":
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("category", ""))
            elif sort_choice == "Dato (nyeste)":
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("created", ""), reverse=True)
            else:  # Dato (ældste)
                sorted_memories = sorted(self.user_memory.items(), 
                                       key=lambda x: x[1].get("created", ""))
            
            for i, (memory_id, memory_data) in enumerate(sorted_memories, 1):
                category = memory_data.get("category", "andet")
                info = memory_data.get("info", "")
                importance = memory_data.get("importance", 0)
                created = memory_data.get("created", "Ukendt")
                
                stars = "⭐" * importance
                text_widget.insert(tk.END, f"{i}. [{category}] {info}\n")
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
        
        memory_summary = "\n\nBruger information (brug dette til personlige svar):\n"
        
        # Organiser efter kategori
        categories = {}
        for memory_data in self.user_memory.values():
            category = memory_data.get("category", "andet")
            if category not in categories:
                categories[category] = []
            categories[category].append(memory_data.get("info", ""))
        
        # Byg summary
        for category, infos in categories.items():
            if infos:
                memory_summary += f"{category}: {', '.join(infos)}\n"
        
        return memory_summary
    
    # Opskrift søgning funktioner
    def search_recipes(self):
        """Start opskrift søgning"""
        query = self.recipe_entry.get().strip()
        if not query:
            messagebox.showwarning("Advarsel", "Indtast hvad du vil søge efter (fx 'pandekager')")
            return
        
        # Start progress bar
        self.search_progress.start()
        self.recipe_listbox.delete(0, tk.END)
        self.recipe_listbox.insert(0, "Søger...")
        
        # Søg i baggrunden
        threading.Thread(target=self._search_recipes_worker, args=(query,), daemon=True).start()
    
    def _search_recipes_worker(self, query):
        """Søg efter opskrifter (kører i baggrunden)"""
        try:
            # Metode 1: Brug TheMealDB API
            results = self.search_themealdb(query)
            
            # Metode 2: Hvis ingen resultater, prøv en generisk søgning
            if not results:
                results = self.search_generic_recipes(query)
            
            self.recipe_search_queue.put(('success', results))
            
        except Exception as e:
            self.recipe_search_queue.put(('error', str(e)))
    
    def search_themealdb(self, query):
        """Søg i TheMealDB API"""
        try:
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if data.get('meals'):
                for meal in data['meals'][:5]:  # Max 5 resultater
                    # Saml ingredienser
                    ingredients = []
                    for i in range(1, 21):
                        ingredient = meal.get(f'strIngredient{i}', '').strip()
                        measure = meal.get(f'strMeasure{i}', '').strip()
                        
                        if ingredient:
                            if measure:
                                ingredients.append(f"{measure} {ingredient}")
                            else:
                                ingredients.append(ingredient)
                    
                    recipe = {
                        'title': meal.get('strMeal', 'Ukendt opskrift'),
                        'ingredients': ingredients,
                        'instructions': meal.get('strInstructions', ''),
                        'category': meal.get('strCategory', ''),
                        'source': 'TheMealDB'
                    }
                    results.append(recipe)
            
            return results
            
        except Exception as e:
            print(f"TheMealDB fejl: {e}")
            return []
    
    def search_generic_recipes(self, query):
        """Generisk opskrift søgning som fallback"""
        # Her kan du implementere andre API'er eller web scraping
        # For nu returnerer vi nogle eksempel opskrifter
        
        example_recipes = {
            'pandekager': [{
                'title': 'Klassiske Pandekager',
                'ingredients': [
                    '3 dl hvedemel',
                    '5 dl mælk',
                    '3 æg',
                    '1 spsk sukker',
                    '1 tsk salt',
                    'Smør til stegning'
                ],
                'instructions': '1. Pisk mel og halvdelen af mælken sammen til en jævn dej. 2. Tilsæt resten af mælken, æg, sukker og salt. 3. Lad dejen hvile 30 min. 4. Steg tynde pandekager på en varm pande med smør.',
                'category': 'Dessert',
                'source': 'Lokal database'
            }],
            'pasta': [{
                'title': 'Pasta Carbonara',
                'ingredients': [
                    '400g spaghetti',
                    '200g bacon',
                    '3 æggeblommer',
                    '1 dl fløde',
                    '100g parmesan',
                    'Salt og peber'
                ],
                'instructions': '1. Kog pasta. 2. Steg bacon sprødt. 3. Pisk æggeblommer, fløde og revet parmesan sammen. 4. Bland den varme pasta med bacon og æggeblandingen. 5. Server straks.',
                'category': 'Hovedret',
                'source': 'Lokal database'
            }]
        }
        
        # Find matchende opskrifter
        query_lower = query.lower()
        for key, recipes in example_recipes.items():
            if key in query_lower or query_lower in key:
                return recipes
        
        return []
    
    def check_recipe_queue(self):
        """Check for opskrift søgeresultater"""
        try:
            while True:
                result_type, data = self.recipe_search_queue.get_nowait()
                
                # Stop progress bar
                self.search_progress.stop()
                
                if result_type == 'success':
                    self.display_recipes(data)
                else:
                    self.recipe_listbox.delete(0, tk.END)
                    self.recipe_listbox.insert(0, f"Fejl: {data}")
        except queue.Empty:
            pass
        
        # Check igen om 100ms
        self.root.after(100, self.check_recipe_queue)
    
    def display_recipes(self, recipes):
        """Vis opskrift resultater"""
        self.recipe_listbox.delete(0, tk.END)
        self.recipes_data = recipes
        
        if recipes:
            for i, recipe in enumerate(recipes):
                title = recipe['title']
                category = recipe.get('category', '')
                if category:
                    display_text = f"{title} ({category})"
                else:
                    display_text = title
                self.recipe_listbox.insert(tk.END, display_text)
        else:
            self.recipe_listbox.insert(0, "Ingen opskrifter fundet")
    
    def read_selected_recipe(self):
        """Læs valgt opskrift højt"""
        selection = self.recipe_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advarsel", "Vælg en opskrift først")
            return
        
        if not self.recipes_data:
            return
        
        recipe = self.recipes_data[selection[0]]
        
        # Format opskrift til oplæsning
        text = f"Opskrift på {recipe['title']}. "
        
        if recipe.get('category'):
            text += f"Kategori: {recipe['category']}. "
        
        if recipe['ingredients']:
            text += "Ingredienser: "
            for ingredient in recipe['ingredients']:
                text += f"{ingredient}. "
        
        if recipe['instructions']:
            text += "Fremgangsmåde: "
            # Rens instruktioner
            instructions = recipe['instructions'].replace('\r\n', '. ').replace('\n', '. ')
            text += instructions
        
        # Send til TTS
        if self.tts_var.get():
            self.speak_text(text)
        
        # Vis også i chat
        self.add_to_chat("Opskrift", text, "system")
    
    # Session Management
    def create_new_session(self):
        """Opret ny session"""
        if not hasattr(self, 'sessions_listbox'):
            session_name = f"Samtale {len(self.sessions) + 1}"
        else:
            session_name = simpledialog.askstring("Ny samtale", "Navn på samtale:", 
                                                 initialvalue=f"Samtale {len(self.sessions) + 1}")
            if not session_name:
                return
        
        session_id = f"{self.current_user}_{int(time.time())}"
        self.sessions[session_id] = {
            "name": session_name,
            "history": [self.system_prompt.copy()],
            "created": datetime.now(),
            "user": self.current_user
        }
        
        self.current_session_id = session_id
        self.conversation_history = self.sessions[session_id]["history"]
        self.message_count = 0
        
        if hasattr(self, 'sessions_listbox'):
            self.refresh_sessions_list()
            self.clear_chat_display()
            self.update_session_label()
            
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
                    self.sessions = {k: v for k, v in all_sessions.items() 
                                   if v.get("user") == self.current_user}
            else:
                self.sessions = {}
        except:
            self.sessions = {}
    
    def load_selected_session(self, event=None):
        """Load valgt session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        if (session_id in self.sessions and 
            self.sessions[session_id].get("user") == self.current_user):
            self.current_session_id = session_id
            self.conversation_history = self.sessions[session_id]["history"]
            self.refresh_chat_from_history()
            self.update_session_label()
            self.message_count = 0
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
        """Slet valgt session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Vælg en samtale at slette")
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
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
        """Gem sessions til fil"""
        try:
            all_sessions = {}
            if os.path.exists(self.sessions_file):
                try:
                    with open(self.sessions_file, 'rb') as f:
                        all_sessions = pickle.load(f)
                except:
                    pass
            
            all_sessions.update(self.sessions)
            
            with open(self.sessions_file, 'wb') as f:
                pickle.dump(all_sessions, f)
        except Exception as e:
            print(f"Fejl ved gemning af sessions: {e}")
    
    def refresh_sessions_list(self):
        """Opdater sessions liste"""
        if not hasattr(self, 'sessions_listbox'):
            return
            
        self.sessions_listbox.delete(0, tk.END)
        
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
            self.tts_engine.setProperty('rate', 130)
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
    
    def start_tts_worker(self):
        """Start TTS worker thread"""
        self.tts_thread = threading.Thread(target=self.tts_worker, daemon=True)
        self.tts_thread.start()
    
    def tts_worker(self):
        """TTS worker der processer queue"""
        while True:
            try:
                text = self.tts_queue.get(timeout=1)
                if text and self.tts_engine and self.tts_var.get():
                    # Rens tekst
                    clean_text = self.clean_text_for_speech(text)
                    self.tts_engine.say(clean_text)
                    self.tts_engine.runAndWait()
                self.tts_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS fejl: {e}")
    
    def clean_text_for_speech(self, text):
        """Rens tekst til bedre udtale"""
        # Fjern emojis og specielle tegn
        text = re.sub(r'[^\w\s\.\,\!\?\-\:]', ' ', text)
        
        # Erstat forkortelser
        replacements = {
            'fx': 'for eksempel',
            'osv': 'og så videre',
            'ml': 'milliliter',
            'dl': 'deciliter',
            'kg': 'kilogram',
            'g': 'gram',
            'tsk': 'teske',
            'spsk': 'spisske',
            '°C': 'grader celsius'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def speak_text(self, text):
        """Send tekst til TTS queue"""
        if text and self.tts_engine:
            self.tts_queue.put(text)
    
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
            recent_messages = self.conversation_history[-12:]
            messages = [{"role": "system", "content": enhanced_system_prompt}] + [msg for msg in recent_messages if msg["role"] != "system"]
            
            data = {
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800,
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
            self.speak_text(response)
    
    def _handle_llm_error(self, error_msg):
        """Håndter LLM fejl (kører i main thread)"""
        self.add_to_chat("System", error_msg, "system")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("❌ Fejl")
        
        # Fjern sidste brugerbesked ved fejl
        if self.conversation_history and self.conversation_history[-1]["role"] == "user":
            self.conversation_history.pop()
    
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
            self.system_prompt["content"] = self.english_prompt
            self.update_status("🇬🇧 Engelsk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på engelsk selvom du skriver dansk.", "system")
        else:
            self.system_prompt["content"] = self.danish_prompt
            self.update_status("🇩🇰 Dansk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på dansk igen.", "system")
        
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
        self.message_count = 0
        
        memory_count = len(self.user_memory)
        if memory_count > 0:
            self.add_to_chat("System", f"Chat ryddet. AI'en husker stadig {memory_count} ting om dig! Start en ny samtale.", "system")
        else:
            self.add_to_chat("System", "Chat ryddet. Start en ny samtale!", "system")
        
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.current_user):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
    
    def run(self):
        """Start GUI"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
    
    def on_closing(self):
        """Håndter lukning af program"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.current_user):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
        
        self.save_sessions()
        self.save_user_memory()
        
        self.root.destroy()

def main():
    """Hovedfunktion"""
    print("🚀 Starter Forbedret LLM Chat GUI...")
    print("✨ Nye forbedringer:")
    print("  - Bedre hukommelse system der fanger personlig info")
    print("  - Fungerende indstillinger")
    print("  - Opskrift søgning med oplæsning")
    print("  - Robust JSON parsing")
    print("  - Forbedret TTS system")
    print("  - Organiseret hukommelse visning")
    app = LLMChatGUI()
    app.run()

if __name__ == "__main__":
    main()