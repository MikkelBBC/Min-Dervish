"""
GUI action metoder for LLM Chat applikationen
Denne fil indeholder alle action metoder for GUI komponenter
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import json

class GUIActions:
    """Mixin class for GUI actions"""
    
    # Session Actions
    def create_new_session(self):
        """Opret ny session"""
        session_name = simpledialog.askstring("Ny samtale", "Navn på samtale:", 
                                             initialvalue=f"Samtale {len(self.session_manager.sessions) + 1}")
        if not session_name:
            return
        
        session_id, name = self.session_manager.create_new_session(session_name)
        self._refresh_sessions_list()
        self.clear_chat_display()
        self._update_session_label()
        
        memory_count = self.memory_manager.get_memory_count()
        if memory_count > 0:
            self.add_to_chat("System", f"Ny samtale '{name}' oprettet! AI'en husker allerede {memory_count} ting om dig.", "system")
        else:
            self.add_to_chat("System", f"Ny samtale '{name}' oprettet!", "system")
    
    def save_current_session(self):
        """Gem aktuel session"""
        if self.session_manager.save_current_session():
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
        
        if session_id in self.session_manager.sessions:
            session_name = self.session_manager.sessions[session_id]["name"]
            if messagebox.askyesno("Bekræft", f"Slet samtale '{session_name}'?"):
                deleted_name = self.session_manager.delete_session(session_id)
                if deleted_name:
                    self._refresh_sessions_list()
                    if self.session_manager.current_session_id == session_id:
                        self.clear_chat_display()
                        self._update_session_label()
    
    def load_selected_session(self, event=None):
        """Load valgt session"""
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        
        session_info = self.sessions_listbox.get(selection[0])
        session_id = session_info.split(" - ")[0]
        
        if self.session_manager.load_session(session_id):
            self._refresh_chat_from_history()
            self._update_session_label()
            self.memory_manager.message_count = 0  # Reset counter for loaded session
        else:
            messagebox.showerror("Adgang nægtet", "Du har ikke adgang til denne samtale!")
    
    # Memory Actions
    def force_update_memory(self):
        """Tving hukommelse opdatering nu"""
        if not self.memory_manager.force_update_memory(self.session_manager.conversation_history):
            messagebox.showinfo("Info", "For få beskeder til at opdatere hukommelse. Chat lidt mere først!")
    
    def show_all_memory(self):
        """Vis alle minder i nyt vindue"""
        memory_window = tk.Toplevel(self.root)
        memory_window.title(f"🧠 Alle Minder - Bruger: {self.user_manager.get_user_id()}")
        memory_window.geometry("700x500")
        
        # Sortering controls
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
            
            if not self.memory_manager.user_memory:
                text_widget.insert(tk.END, "Ingen minder endnu.")
                text_widget.config(state=tk.DISABLED)
                return
            
            # Sorter baseret på valg
            sort_choice = sort_var.get()
            if sort_choice == "Vigtighed":
                sorted_memories = self.memory_manager.get_sorted_memories("importance")
            elif sort_choice == "Dato (nyeste)":
                sorted_memories = self.memory_manager.get_sorted_memories("date_newest")
            else:  # Dato (ældste)
                sorted_memories = self.memory_manager.get_sorted_memories("date_oldest")
            
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
            self.memory_manager.clear_all_memory()
            self.add_to_chat("System", "🧹 Alle minder er slettet!", "system")
    
    # Audio Actions
    def toggle_voice_input(self):
        """Toggle stemme input"""
        if self.audio_manager.is_listening:
            return
        
        if not self.audio_manager.is_microphone_available():
            messagebox.showerror("Fejl", "Mikrofon ikke tilgængelig")
            return
        
        self.voice_button.config(state=tk.DISABLED, text="🎤 Lytter...")
        self.audio_manager.start_voice_input()
    
    def toggle_tts(self):
        """Toggle TTS"""
        enabled = self.tts_var.get()
        self.audio_manager.set_tts_enabled(enabled)
        status = "TIL" if enabled else "FRA"
        self.update_status(f"🔊 TTS: {status}")
    
    def toggle_english_response(self):
        """Toggle engelsk respons mode"""
        enabled = self.english_var.get()
        self.session_manager.set_english_mode(enabled)
        
        if enabled:
            self.update_status("🇬🇧 Engelsk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på engelsk selvom du skriver dansk.", "system")
        else:
            self.update_status("🇩🇰 Dansk svar: TIL")
            self.add_to_chat("System", "Modellen vil nu svare på dansk igen.", "system")
    
    def toggle_auto_memory(self):
        """Toggle automatiske minder"""
        enabled = self.auto_memory_var.get()
        self.memory_manager.set_auto_memory_enabled(enabled)
        
        status = "Aktiveret" if enabled else "Deaktiveret"
        self.auto_memory_label.config(text=f"🤖 Auto-hukommelse: {status}")
        
        if enabled:
            self.add_to_chat("System", "🤖 Automatisk hukommelse aktiveret!", "system")
        else:
            self.add_to_chat("System", "🤖 Automatisk hukommelse deaktiveret.", "system")
    
    # Chat Actions
    def clear_chat(self):
        """Ryd chat historie"""
        self.session_manager.clear_conversation()
        self.clear_chat_display()
        self.memory_manager.message_count = 0  # Reset message counter
        
        memory_count = self.memory_manager.get_memory_count()
        if memory_count > 0:
            self.add_to_chat("System", f"Chat ryddet. AI'en husker stadig {memory_count} ting om dig! Start en ny samtale.", "system")
        else:
            self.add_to_chat("System", "Chat ryddet. Start en ny samtale!", "system")
    
    def clear_chat_display(self):
        """Ryd kun chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    # Settings Actions
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
        timeout_enabled_var = tk.BooleanVar(value=self.llm_client.timeout_enabled)
        ttk.Checkbutton(timeout_frame, text="Aktiver timeout", 
                       variable=timeout_enabled_var).pack(anchor=tk.W, pady=(0, 5))
        
        # Timeout slider
        ttk.Label(timeout_frame, text="Timeout sekunder:").pack(anchor=tk.W)
        timeout_frame_inner = ttk.Frame(timeout_frame)
        timeout_frame_inner.pack(fill=tk.X, pady=5)
        
        timeout_var = tk.IntVar(value=self.llm_client.timeout_seconds)
        timeout_scale = tk.Scale(timeout_frame_inner, from_=10, to=120, 
                               orient=tk.HORIZONTAL, variable=timeout_var)
        timeout_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        timeout_label = ttk.Label(timeout_frame_inner, text=f"{self.llm_client.timeout_seconds}s")
        timeout_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Bind scale update
        timeout_scale.bind("<Motion>", lambda e: timeout_label.config(text=f"{timeout_var.get()}s"))
        
        # Auto-hukommelse indstillinger
        memory_frame = ttk.LabelFrame(settings_window, text="🧠 Hukommelse Indstillinger", padding="10")
        memory_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(memory_frame, text="Opdater hukommelse hver X besked:").pack(anchor=tk.W)
        memory_threshold_frame = ttk.Frame(memory_frame)
        memory_threshold_frame.pack(fill=tk.X, pady=5)
        
        memory_threshold_var = tk.IntVar(value=self.memory_manager.auto_memory_threshold)
        memory_threshold_scale = tk.Scale(memory_threshold_frame, from_=1, to=10, 
                                        orient=tk.HORIZONTAL, variable=memory_threshold_var)
        memory_threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        memory_threshold_label = ttk.Label(memory_threshold_frame, text=f"{self.memory_manager.auto_memory_threshold}")
        memory_threshold_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        memory_threshold_scale.bind("<Motion>", lambda e: memory_threshold_label.config(text=f"{memory_threshold_var.get()}"))
        
        # Gem og luk knapper
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_settings():
            # Gem LLM indstillinger
            self.llm_client.set_timeout_settings(timeout_enabled_var.get(), timeout_var.get())
            self.memory_manager.set_timeout_settings(timeout_enabled_var.get(), timeout_var.get())
            
            # Gem memory indstillinger
            self.memory_manager.set_auto_memory_threshold(memory_threshold_var.get())
            
            settings_window.destroy()
            self.add_to_chat("System", f"⚙️ Indstillinger gemt! Timeout: {'ON' if timeout_enabled_var.get() else 'OFF'} ({timeout_var.get()}s), Hukommelse: hver {memory_threshold_var.get()}. besked", "system")
        
        ttk.Button(button_frame, text="💾 Gem", command=save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="❌ Annuller", command=settings_window.destroy).pack(side=tk.RIGHT)
    
    # Display Update Methods
    def _refresh_sessions_list(self):
        """Opdater sessions liste"""
        if not hasattr(self, 'sessions_listbox'):
            return
        
        self.sessions_listbox.delete(0, tk.END)
        
        user_sessions = self.session_manager.get_user_sessions()
        for session_id, session_data in user_sessions:
            created_str = session_data["created"].strftime("%d/%m %H:%M")
            msg_count = self.session_manager.get_message_count_for_session(session_id)
            display_text = f"{session_id} - {session_data['name']} ({msg_count} beskeder, {created_str})"
            self.sessions_listbox.insert(0, display_text)
    
    def _refresh_memory_display(self):
        """Opdater hukommelse display"""
        if not hasattr(self, 'memory_display'):
            return
        
        self.memory_display.config(state=tk.NORMAL)
        self.memory_display.delete("1.0", tk.END)
        
        if self.memory_manager.user_memory:
            # Sorter efter vigtighed og dato
            sorted_memories = self.memory_manager.get_sorted_memories("importance")
            
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
    
    def _update_memory_counter(self):
        """Opdater memory tæller"""
        if hasattr(self, 'note_counter_label'):
            total_memories = self.memory_manager.get_memory_count()
            self.note_counter_label.config(text=f"🧠 Minder: {total_memories}")
    
    def _update_session_label(self):
        """Opdater session label"""
        name = self.session_manager.get_current_session_name()
        self.session_name_label.config(text=f"📝 Aktuel: {name}")
    
    def _refresh_chat_from_history(self):
        """Genopbyg chat fra historie"""
        self.clear_chat_display()
        
        for msg in self.session_manager.conversation_history:
            if msg["role"] == "user":
                self.add_to_chat("Du", msg["content"], "user")
            elif msg["role"] == "assistant":
                self.add_to_chat("Assistant", msg["content"], "assistant")
    
    # Application lifecycle
    def on_closing(self):
        """Håndter lukning af program"""
        # Gem aktuel session
        self.session_manager.save_current_session()
        
        # Gem alle data
        self.session_manager.save_sessions()
        self.memory_manager.save_user_memory()
        
        self.root.destroy()
    
    def run(self):
        """Start GUI"""
        try:
            # Gem sessions når programmet lukkes
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            pass