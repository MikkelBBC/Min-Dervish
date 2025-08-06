"""
Main Window - Hoved GUI vindue
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
from datetime import datetime
from typing import Optional
import requests

import config
from core import LLMClient, MemoryManager, SessionManager
from services import TTSService, SpeechRecognitionService
from utils import UserManager
from .chat_widget import ChatWidget
from .memory_widget import MemoryWidget
from .settings_dialog import SettingsDialog

class LLMChatGUI:
    def __init__(self):
        # Bruger setup
        self.current_user = UserManager.get_or_create_user()
        self.user_data_dir = UserManager.get_user_data_dir(self.current_user)
        UserManager.ensure_user_directory(self.user_data_dir)
        
        # Core komponenter
        self.llm_client = LLMClient()
        self.memory_manager = MemoryManager(self.current_user, self.user_data_dir)
        self.session_manager = SessionManager(self.current_user, self.user_data_dir)
        
        # Services
        self.tts_service = TTSService()
        self.speech_service = SpeechRecognitionService()
        
        # System prompt
        self.system_prompt = {
            "role": "system",
            "content": config.DANISH_PROMPT
        }
        
        # GUI variabler
        self.auto_memory_enabled = True
        self.english_mode = False
        
        # Setup GUI
        self.setup_gui()
        
        # Start med ny session
        self.create_new_session()
        
        # Initialiser services
        self.init_services()
        
        # Test forbindelse
        self.test_connection()
    
    def setup_gui(self):
        """Opret GUI vindue"""
        self.root = tk.Tk()
        self.root.title(f"{config.WINDOW_TITLE} - Bruger: {self.current_user}")
        self.root.geometry(config.WINDOW_SIZE)
        self.root.configure(bg=config.WINDOW_BG_COLOR)
        
        # Hovedframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top panel
        self.setup_top_panel(main_frame)
        
        # Chat område
        self.chat_widget = ChatWidget(main_frame)
        self.chat_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Input område
        self.setup_input_area(main_frame)
        
        # Kontrol panel
        self.setup_control_panel(main_frame)
        
        # Initial updates
        self.refresh_sessions_list()
        self.memory_widget.refresh_display(self.memory_manager.user_memory)
        
        # Velkomstbesked
        welcome_msg = config.WELCOME_MESSAGE.format(user=self.current_user)
        self.chat_widget.add_message("System", welcome_msg, "system")
    
    def setup_top_panel(self, parent):
        """Setup top panel med sessions og hukommelse"""
        top_panel = ttk.Frame(parent)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        
        # Sessions panel
        sessions_frame = ttk.LabelFrame(top_panel, text="📁 Mine Samtaler", padding="5")
        sessions_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Session controls
        sessions_controls = ttk.Frame(sessions_frame)
        sessions_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(sessions_controls, text="➕ Ny", 
                  command=self.create_new_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sessions_controls, text="💾 Gem", 
                  command=self.save_current_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sessions_controls, text="🗑️ Slet", 
                  command=self.delete_session, width=8).pack(side=tk.LEFT, padx=(0, 5))
        
        # Sessions liste
        self.sessions_listbox = tk.Listbox(sessions_frame, height=4, font=("Arial", 10))
        self.sessions_listbox.pack(fill=tk.BOTH, expand=True)
        self.sessions_listbox.bind('<Double-Button-1>', self.load_selected_session)
        
        # Memory widget
        self.memory_widget = MemoryWidget(top_panel, self.memory_manager)
        self.memory_widget.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    def setup_input_area(self, parent):
        """Setup input område"""
        input_frame = ttk.LabelFrame(parent, text="✏️ Skriv besked", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        input_row = ttk.Frame(input_frame)
        input_row.pack(fill=tk.X)
        
        self.input_entry = tk.Text(input_row, height=3, font=config.CHAT_FONT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.input_entry.bind("<Control-Return>", lambda e: self.send_message())
        
        button_frame = ttk.Frame(input_row)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.send_button = ttk.Button(button_frame, text="📤 Send", 
                                     command=self.send_message, width=10)
        self.send_button.pack(fill=tk.X, pady=(0, 5))
        
        self.voice_button = ttk.Button(button_frame, text="🎤 Tal", 
                                      command=self.toggle_voice_input, width=10)
        self.voice_button.pack(fill=tk.X, pady=(0, 5))
    
    def setup_control_panel(self, parent):
        """Setup kontrol panel"""
        control_frame = ttk.LabelFrame(parent, text="🎛️ Kontroller", padding="5")
        control_frame.pack(fill=tk.X)
        
        controls_row = ttk.Frame(control_frame)
        controls_row.pack(fill=tk.X)
        
        # TTS toggle
        self.tts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_row, text="🔊 Oplæsning", 
                       variable=self.tts_var,
                       command=self.toggle_tts).pack(side=tk.LEFT, padx=(0, 20))
        
        # English toggle
        self.english_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls_row, text="🇬🇧 Engelsk svar", 
                       variable=self.english_var,
                       command=self.toggle_english_response).pack(side=tk.LEFT, padx=(0, 20))
        
        # Auto-memory toggle
        self.auto_memory_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_row, text="🧠 Auto-hukommelse", 
                       variable=self.auto_memory_var,
                       command=self.toggle_auto_memory).pack(side=tk.LEFT, padx=(0, 20))
        
        # Clear chat button
        ttk.Button(controls_row, text="🧹 Ryd chat", 
                  command=self.clear_chat).pack(side=tk.LEFT, padx=(0, 10))
        
        # Settings button
        ttk.Button(controls_row, text="⚙️ Indstillinger", 
                  command=self.open_settings).pack(side=tk.LEFT, padx=(0, 10))
        
        # Info labels
        info_frame = ttk.Frame(controls_row)
        info_frame.pack(side=tk.LEFT, padx=(20, 10))
        
        self.session_name_label = ttk.Label(info_frame, text="📝 Aktuel: Ny samtale", 
                                           font=("Arial", 10, "italic"))
        self.session_name_label.pack(anchor=tk.W)
        
        self.user_label = ttk.Label(info_frame, text=f"👤 Bruger: {self.current_user}", 
                                   font=("Arial", 8, "italic"))
        self.user_label.pack(anchor=tk.W)
        
        # Status frame
        status_frame = ttk.Frame(controls_row)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = ttk.Label(status_frame, text="🟡 Starter...")
        self.status_label.pack(anchor=tk.E)
        
        self.note_counter_label = ttk.Label(status_frame, text="🧠 Minder: 0", 
                                           font=("Arial", 8, "italic"))
        self.note_counter_label.pack(anchor=tk.E)
    
    def init_services(self):
        """Initialiser services"""
        # TTS
        success, msg = self.tts_service.init_engine()
        self.update_status(msg)
        
        # Speech Recognition
        success, msg = self.speech_service.init_microphone()
        self.update_status(msg)
    
    def test_connection(self):
        """Test LLM forbindelse"""
        def test():
            success, msg = self.llm_client.test_connection()
            self.root.after(0, self.update_status, msg)
        
        threading.Thread(target=test, daemon=True).start()
    
    def send_message(self):
        """Send besked til LLM"""
        message = self.input_entry.get("1.0", tk.END).strip()
        if not message:
            return
        
        self.input_entry.delete("1.0", tk.END)
        self.chat_widget.add_message("Du", message, "user")
        
        self.send_button.config(state=tk.DISABLED, text="⏳ Sender...")
        
        threading.Thread(target=self._send_to_llm, args=(message,), daemon=True).start()
    
    def _send_to_llm(self, prompt):
        """Send besked til LLM (baggrund)"""
        try:
            # Byg enhanced system prompt
            enhanced_prompt = self.system_prompt["content"]
            memory_summary = self.memory_manager.get_memories_for_prompt()
            if memory_summary:
                enhanced_prompt += memory_summary
            
            # Tilføj til historie
            self.session_manager.add_message("user", prompt)
            
            # Byg messages
            recent_messages = self.session_manager.get_recent_messages()
            messages = [{"role": "system", "content": enhanced_prompt}] + \
                      [msg for msg in recent_messages if msg["role"] != "system"]
            
            self.update_status("🤖 Tænker...")
            
            # Send til LLM
            result = self.llm_client.send_message(messages)
            response = self.llm_client.extract_response(result)
            
            # Tilføj svar til historie
            self.session_manager.add_message("assistant", response)
            
            # Opdater GUI
            self.root.after(0, self._handle_llm_response, response)
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout efter {self.llm_client.timeout_seconds}s"
            self.root.after(0, self._handle_llm_error, error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Kan ikke forbinde til LLM"
            self.root.after(0, self._handle_llm_error, error_msg)
        except Exception as e:
            error_msg = f"Fejl: {str(e)}"
            self.root.after(0, self._handle_llm_error, error_msg)
    
    def _handle_llm_response(self, response):
        """Håndter LLM respons"""
        self.chat_widget.add_message("Assistant", response, "assistant")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("✅ Klar")
        
        # Check auto-memory
        if self.auto_memory_enabled:
            if self.memory_manager.increment_message_count():
                self.memory_widget.set_status("🔄 Analyserer samtale...")
                threading.Thread(target=self._auto_update_memory, daemon=True).start()
            else:
                count = self.memory_manager.message_count
                threshold = self.memory_manager.auto_memory_threshold
                self.memory_widget.set_status(f"🤖 Auto-hukommelse: {count}/{threshold}")
        
        # TTS
        if self.tts_var.get():
            self.tts_service.speak(response)
    
    def _handle_llm_error(self, error_msg):
        """Håndter LLM fejl"""
        self.chat_widget.add_message("System", error_msg, "system")
        self.send_button.config(state=tk.NORMAL, text="📤 Send")
        self.update_status("❌ Fejl")
        
        # Fjern sidste besked
        if self.session_manager.conversation_history[-1]["role"] == "user":
            self.session_manager.conversation_history.pop()
    
    def _auto_update_memory(self):
        """Auto-opdater hukommelse"""
        try:
            # Få seneste beskeder
            recent = self.session_manager.get_recent_messages(config.MEMORY_ANALYSIS_MESSAGES)
            conversation_text = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in recent 
                if msg["role"] in ["user", "assistant"]
            ])
            
            if len(conversation_text.split("\n")) < 2:
                return
            
            # Analyser med LLM
            memory_data = self.llm_client.analyze_for_memory(conversation_text)
            
            if memory_data:
                new_count = self.memory_manager.process_memory_updates(memory_data)
                
                if new_count > 0:
                    self.root.after(0, self._handle_memory_update, new_count)
                else:
                    self.root.after(0, self.memory_widget.set_status, 
                                  "🤖 Ingen nye minder denne gang")
                    
        except Exception as e:
            print(f"Auto-memory error: {e}")
            self.root.after(0, self.memory_widget.set_status, "❌ Hukommelse fejl")
    
    def _handle_memory_update(self, new_count):
        """Håndter hukommelse opdatering"""
        self.memory_widget.refresh_display(self.memory_manager.user_memory)
        self.update_memory_counter()
        self.memory_widget.set_status(f"✅ {new_count} nye minder!")
        
        # Reset status efter 3 sekunder
        self.root.after(3000, self.memory_widget.set_status, "🤖 Auto-hukommelse: Aktiveret")
    
    def create_new_session(self):
        """Opret ny session"""
        if hasattr(self, 'sessions_listbox'):
            name = simpledialog.askstring("Ny samtale", "Navn på samtale:", 
                                         initialvalue=f"{config.SESSION_NAME_PREFIX} {len(self.session_manager.sessions) + 1}")
            if not name:
                return
        else:
            name = f"{config.SESSION_NAME_PREFIX} {len(self.session_manager.sessions) + 1}"
        
        self.session_manager.create_session(name, self.system_prompt)
        self.memory_manager.reset_message_count()
        
        if hasattr(self, 'sessions_listbox'):
            self.refresh_sessions_list()
            self.chat_widget.clear()
            self.update_session_label()
            
            memory_count = self.memory_manager.get_memory_count()
            if memory_count > 0:
                msg = f"Ny samtale '{name}' oprettet! AI'en husker allerede {memory_count} ting om dig."
            else:
                msg = f"Ny samtale '{name}' oprettet!"
            self.chat_widget.add_message("System", msg, "system")
    
    def refresh_sessions_list(self):
        """Opdater sessions liste"""
        if not hasattr(self, 'sessions_listbox'):
            return
        
        self.sessions_listbox.delete(0, tk.END)
        
        user_sessions = self.session_manager.get_user_sessions()
        for session_id, session_data in sorted(user_sessions.items(), 
                                              key=lambda x: x[1]["created"], reverse=True):
            info = self.session_manager.get_session_info(session_id)
            if info:
                created_str = info["created"].strftime("%d/%m %H:%M")
                display_text = f"{session_id} - {info['name']} ({info['message_count']} beskeder, {created_str})"
                self.sessions_listbox.insert(0, display_text)
    
    def update_status(self, message):
        """Opdater status label"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    def update_memory_counter(self):
        """Opdater memory counter"""
        if hasattr(self, 'note_counter_label'):
            count = self.memory_manager.get_memory_count()
            self.note_counter_label.config(text=f"🧠 Minder: {count}")
    
    def update_session_label(self):
        """Opdater session label"""
        session = self.session_manager.get_current_session()
        if session:
            self.session_name_label.config(text=f"📝 Aktuel: {session['name']}")
    
    def toggle_voice_input(self):
        """Toggle voice input"""
        if self.speech_service.is_currently_listening():
            return
        
        if not self.speech_service.is_available():
            messagebox.showerror("Fejl", "Mikrofon ikke tilgængelig")
            return
        
        self.voice_button.config(state=tk.DISABLED, text="🎤 Lytter...")
        self.speech_service.listen_for_speech(self._handle_voice_result)
    
    def _handle_voice_result(self, text):
        """Håndter voice result"""
        self.root.after(0, self._update_voice_ui, text)
    
    def _update_voice_ui(self, text):
        """Opdater voice UI"""
        self.voice_button.config(state=tk.NORMAL, text="🎤 Tal")
        
        if text:
            self.input_entry.insert(tk.END, text)
            self.chat_widget.add_message("System", f"Genkendt: {text}", "system")
        else:
            self.chat_widget.add_message("System", "Kunne ikke genkende tale", "system")
    
    def toggle_english_response(self):
        """Toggle engelsk response"""
        if self.english_var.get():
            self.system_prompt["content"] = config.ENGLISH_PROMPT
            self.update_status("🇬🇧 Engelsk svar: TIL")
            self.chat_widget.add_message("System", "Modellen vil nu svare på engelsk", "system")
        else:
            self.system_prompt["content"] = config.DANISH_PROMPT
            self.update_status("🇩🇰 Dansk svar: TIL")
            self.chat_widget.add_message("System", "Modellen vil nu svare på dansk", "system")
        
        if self.session_manager.conversation_history and \
           self.session_manager.conversation_history[0]["role"] == "system":
            self.session_manager.conversation_history[0] = self.system_prompt.copy()
    
    def toggle_tts(self):
        """Toggle TTS"""
        self.tts_service.toggle(self.tts_var.get())
        status = "TIL" if self.tts_var.get() else "FRA"
        self.update_status(f"🔊 TTS: {status}")
    
    def toggle_auto_memory(self):
        """Toggle auto memory"""
        self.auto_memory_enabled = self.auto_memory_var.get()
        status = "Aktiveret" if self.auto_memory_enabled else "Deaktiveret"
        self.memory_widget.set_status(f"🤖 Auto-hukommelse: {status}")
        self.chat_widget.add_message("System", f"🤖 Automatisk hukommelse {status.lower()}", "system")
    
    def clear_chat(self):
        """Clear chat"""
        self.session_manager.clear_current_history(self.system_prompt)
        self.chat_widget.clear()
        self.memory_manager.reset_message_count()
        
        memory_count = self.memory_manager.get_memory_count()
        if memory_count > 0:
            msg = config.CHAT_CLEARED_WITH_MEMORIES.format(count=memory_count)
        else:
            msg = config.CHAT_CLEARED_NO_MEMORIES
        self.chat_widget.add_message("System", msg, "system")
    
    def save_current_session(self):
        """Gem current session"""
        if self.session_manager.save_current_session():
            self.chat_widget.add_message("System", "Samtale gemt! 💾", "system")
        else:
            messagebox.showwarning("Advarsel", "Ingen valid samtale at gemme")
    
    def load_selected_session(self, event=None):
        """Load selected session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        if self.session_manager.load_session(session_id):
            self.chat_widget.refresh_from_history(self.session_manager.conversation_history)
            self.update_session_label()
            self.memory_manager.reset_message_count()
        else:
            messagebox.showerror("Adgang nægtet", "Du har ikke adgang til denne samtale!")
    
    def delete_session(self):
        """Slet session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Vælg en samtale at slette")
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        session = self.session_manager.get_session_info(session_id)
        if session and messagebox.askyesno("Bekræft", f"Slet samtale '{session['name']}'?"):
            if self.session_manager.delete_session(session_id):
                if self.session_manager.current_session_id == session_id:
                    self.create_new_session()
                self.refresh_sessions_list()
            else:
                messagebox.showerror("Fejl", "Kunne ikke slette samtale")
    
    def open_settings(self):
        """Åbn settings dialog"""
        dialog = SettingsDialog(self.root, self.llm_client, self.memory_manager)
        if dialog.result:
            msg = f"⚙️ Indstillinger gemt! Timeout: {'ON' if dialog.result['timeout_enabled'] else 'OFF'}"
            msg += f" ({dialog.result['timeout_seconds']}s)"
            msg += f", Hukommelse: hver {dialog.result['memory_threshold']}. besked"
            self.chat_widget.add_message("System", msg, "system")
    
    def run(self):
        """Start GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing"""
        self.session_manager.save_current_session()
        self.memory_manager.save_memory()
        self.tts_service.cleanup()
        self.root.destroy()