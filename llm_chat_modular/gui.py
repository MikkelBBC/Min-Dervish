"""
Hovedgrafisk interface for LLM Chat applikationen
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
from datetime import datetime
import json

from config import Config
from user_manager import UserManager
from session_manager import SessionManager
from memory_manager import MemoryManager
from audio_manager import AudioManager
from llm_client import LLMClient

class LLMChatGUI:
    """Hovedapplikation GUI"""
    
    def __init__(self, llm_url=None):
        # Initialiser managers
        self.user_manager = UserManager()
        self.llm_client = LLMClient(llm_url)
        self.session_manager = SessionManager(
            self.user_manager.get_sessions_file_path(),
            self.user_manager.get_user_id()
        )
        self.memory_manager = MemoryManager(
            self.user_manager.get_memory_file_path(),
            self.llm_client.llm_url
        )
        self.audio_manager = AudioManager()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # GUI komponenter
        self.root = None
        self.setup_gui()
        
        # Start med ny session
        self.session_manager.create_new_session()
        
        # Test forbindelse
        self.llm_client.test_connection()
    
    def _setup_callbacks(self):
        """Setup callbacks mellem komponenter"""
        # LLM callbacks
        self.llm_client.set_callbacks(
            on_response=self._handle_llm_response,
            on_error=self._handle_llm_error,
            on_status_update=self.update_status
        )
        
        # Memory callbacks
        self.memory_manager.set_callbacks(
            on_memory_updated=self._handle_memory_updated,
            on_status_update=self._handle_memory_status_update
        )
        
        # Audio callbacks
        self.audio_manager.set_callbacks(
            on_status_update=self.update_status,
            on_voice_result=self._handle_voice_result
        )
    
    def setup_gui(self):
        """Opret GUI vindue"""
        self.root = tk.Tk()
        self.root.title(f"🤖 LLM Chat - Bruger: {self.user_manager.get_user_id()}")
        self.root.geometry(Config.WINDOW_SIZE)
        self.root.configure(bg=Config.WINDOW_BG)
        
        # Hovedframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup GUI komponenter
        self._setup_top_panel(main_frame)
        self._setup_chat_area(main_frame)
        self._setup_input_area(main_frame)
        self._setup_control_panel(main_frame)
        
        # Load og opdater displays
        self._refresh_all_displays()
        
        # Tilføj velkomstbesked
        self._add_welcome_message()
    
    def _setup_top_panel(self, parent):
        """Setup top panel med sessions og hukommelse"""
        top_panel = ttk.Frame(parent)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        
        # Sessions panel
        self._setup_sessions_panel(top_panel)
        
        # Memory panel
        self._setup_memory_panel(top_panel)
    
    def _setup_sessions_panel(self, parent):
        """Setup sessions panel"""
        sessions_frame = ttk.LabelFrame(parent, text="📁 Mine Samtaler", padding="5")
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
    
    def _setup_memory_panel(self, parent):
        """Setup memory panel"""
        memory_frame = ttk.LabelFrame(parent, text="🧠 AI Hukommelse (Permanent)", padding="5")
        memory_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Memory controls
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
    
    def _setup_chat_area(self, parent):
        """Setup chat område"""
        chat_frame = ttk.LabelFrame(parent, text="💬 Samtale", padding="5")
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
        
        # Konfigurer chat farver
        self._configure_chat_tags()
    
    def _setup_input_area(self, parent):
        """Setup input område"""
        input_frame = ttk.LabelFrame(parent, text="✏️ Skriv besked", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        input_row = ttk.Frame(input_frame)
        input_row.pack(fill=tk.X)
        
        self.input_entry = tk.Text(input_row, height=3, font=("Arial", 11))
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.input_entry.bind("<Control-Return>", lambda e: self.send_message())
        
        button_frame = ttk.Frame(input_row)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.send_button = ttk.Button(button_frame, text="📤 Send", command=self.send_message, width=10)
        self.send_button.pack(fill=tk.X, pady=(0, 5))
        
        self.voice_button = ttk.Button(button_frame, text="🎤 Tal", command=self.toggle_voice_input, width=10)
        self.voice_button.pack(fill=tk.X, pady=(0, 5))
    
    def _setup_control_panel(self, parent):
        """Setup kontrol panel"""
        control_frame = ttk.LabelFrame(parent, text="🎛️ Kontroller", padding="5")
        control_frame.pack(fill=tk.X)
        
        controls_row = ttk.Frame(control_frame)
        controls_row.pack(fill=tk.X)
        
        # Checkboxes
        self._setup_control_checkboxes(controls_row)
        
        # Buttons
        ttk.Button(controls_row, text="🧹 Ryd chat", command=self.clear_chat).pack(side=tk.LEFT, padx=(0, 10))
        
        # Info labels
        self._setup_info_labels(controls_row)
        
        # Status labels
        self._setup_status_labels(controls_row)
    
    def _setup_control_checkboxes(self, parent):
        """Setup kontrol checkboxes"""
        # TTS toggle
        self.tts_var = tk.BooleanVar(value=True)
        self.tts_checkbox = ttk.Checkbutton(parent, text="🔊 Oplæsning", variable=self.tts_var, command=self.toggle_tts)
        self.tts_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
        # English response toggle
        self.english_var = tk.BooleanVar(value=False)
        self.english_checkbox = ttk.Checkbutton(parent, text="🇬🇧 Engelsk svar", variable=self.english_var, command=self.toggle_english_response)
        self.english_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        
        # Auto-memory toggle
        self.auto_memory_var = tk.BooleanVar(value=True)
        self.auto_memory_checkbox = ttk.Checkbutton(parent, text="🧠 Auto-hukommelse", variable=self.auto_memory_var, command=self.toggle_auto_memory)
        self.auto_memory_checkbox.pack(side=tk.LEFT, padx=(0, 20))
    
    def _setup_info_labels(self, parent):
        """Setup info labels"""
        info_frame = ttk.Frame(parent)
        info_frame.pack(side=tk.LEFT, padx=(20, 10))
        
        self.session_name_label = ttk.Label(info_frame, text="📝 Aktuel: Ny samtale", font=("Arial", 10, "italic"))
        self.session_name_label.pack(anchor=tk.W)
        
        self.user_label = ttk.Label(info_frame, text=f"👤 Bruger: {self.user_manager.get_user_id()}", font=("Arial", 8, "italic"))
        self.user_label.pack(anchor=tk.W)
    
    def _setup_status_labels(self, parent):
        """Setup status labels"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = ttk.Label(status_frame, text="🟡 Starter...")
        self.status_label.pack(anchor=tk.E)
        
        self.note_counter_label = ttk.Label(status_frame, text="🧠 Minder: 0", font=("Arial", 8, "italic"))
        self.note_counter_label.pack(anchor=tk.E)
    
    def _configure_chat_tags(self):
        """Konfigurer chat farver"""
        self.chat_display.tag_config("system_sender", foreground="purple", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("system_msg", foreground="purple")
        self.chat_display.tag_config("user_sender", foreground="blue", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("user_msg", foreground="black")
        self.chat_display.tag_config("assistant_sender", foreground="green", font=("Arial", 11, "bold"))
        self.chat_display.tag_config("assistant_msg", foreground="dark green")
    
    def _refresh_all_displays(self):
        """Opdater alle displays"""
        self._refresh_sessions_list()
        self._refresh_memory_display()
        self._update_memory_counter()
        self._update_session_label()
    
    def _add_welcome_message(self):
        """Tilføj velkomstbesked"""
        welcome_msg = f"""Velkommen! Du er logget ind som bruger {self.user_manager.get_user_id()}.
AI'en husker automatisk information om dig mellem samtaler.
Ctrl+Enter for at sende besked."""
        self.add_to_chat("System", welcome_msg, "system")
    
    # Event handlers
    def _handle_llm_response(self, response, user_message):
        """Håndter LLM respons"""
        self.session_manager.add_message("assistant", response)
        self.add_to_chat("Assistant", response, "assistant")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("✅ Klar")
        
        # Tjek for automatisk hukommelse opdatering
        if self.memory_manager.check_auto_memory_update():
            self.memory_manager.auto_update_memory(self.session_manager.conversation_history)
        
        # Oplæs hvis aktiveret
        if self.tts_var.get():
            self.audio_manager.speak(response)
    
    def _handle_llm_error(self, error_msg, user_message):
        """Håndter LLM fejl"""
        self.add_to_chat("System", error_msg, "system")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("❌ Fejl")
        
        # Fjern sidste brugerbesked ved fejl
        if (self.session_manager.conversation_history and 
            self.session_manager.conversation_history[-1]["role"] == "user"):
            self.session_manager.conversation_history.pop()
    
    def _handle_memory_updated(self):
        """Håndter memory opdatering"""
        self._refresh_memory_display()
        self._update_memory_counter()
    
    def _handle_memory_status_update(self, status, temp=False):
        """Håndter memory status opdatering"""
        self.auto_memory_label.config(text=status)
        if temp:
            # Reset til normal status efter 3 sekunder
            self.root.after(3000, lambda: self.auto_memory_label.config(text="🤖 Auto-hukommelse: Aktiveret"))
    
    def _handle_voice_result(self, text, error):
        """Håndter stemme resultat"""
        self.voice_button.config(state=tk.NORMAL, text="🎤 Tal")
        
        if text:
            self.input_entry.insert(tk.END, text)
            self.add_to_chat("System", f"Genkendt: {text}", "system")
        else:
            self.add_to_chat("System", f"Stemme fejl: {error}", "system")
    
    # GUI Actions
    def send_message(self):
        """Send besked til LLM"""
        message = self.input_entry.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Ryd input felt
        self.input_entry.delete("1.0", tk.END)
        
        # Tilføj til chat og session
        self.add_to_chat("Du", message, "user")
        self.session_manager.add_message("user", message)
        
        # Disable send button mens vi venter
        self.send_button.config(state=tk.DISABLED, text="⏳ Sender...")
        
        # Forbered beskeder til LLM
        memory_summary = self.memory_manager.get_memory_for_ai()
        system_prompt = self.session_manager.get_system_prompt_with_memory(memory_summary)
        recent_messages = self.session_manager.get_recent_messages()
        
        # Fjern system prompts fra recent_messages og tilføj den aktuelle
        messages = [system_prompt] + [msg for msg in recent_messages if msg["role"] != "system"]
        
        # Send til LLM
        self.llm_client.send_message_async(messages, message)
    
    def add_to_chat(self, sender, message, msg_type="user"):
        """Tilføj besked til chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if msg_type == "system":
            self.chat_display.insert(tk.END, f"[{timestamp}] {sender}: ", "system_sender")
            self.chat_display.insert(tk.END, f"{message}\n\n", "system_msg")
        elif msg_type == "user":
            self.chat_display.insert(tk.END, f"[{timestamp}] Du: ", "user_sender")
            self.chat_display.insert(tk.END, f"{message}\n", "user_msg")
        else:  # assistant
            self.chat_display.insert(tk.END, f"[{timestamp}] 🤖 Assistant: ", "assistant_sender")
            self.chat_display.insert(tk.END, f"{message}\n\n", "assistant_msg")
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def update_status(self, message):
        """Opdater status label"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    # Fortsættelse følger i næste del...