"""
Chat Widget - Håndterer chat display
"""
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
import config

class ChatWidget(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setup_widget()
    
    def setup_widget(self):
        """Setup chat widget"""
        chat_frame = tk.LabelFrame(self, text="💬 Samtale", padx=5, pady=5)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            height=15,
            font=config.CHAT_FONT,
            bg=config.CHAT_BG_COLOR,
            fg=config.CHAT_FG_COLOR
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Setup text tags for colors
        self.setup_tags()
    
    def setup_tags(self):
        """Setup text tags for different message types"""
        self.chat_display.tag_config("system_sender", 
                                    foreground="purple", 
                                    font=(config.CHAT_FONT[0], config.CHAT_FONT[1],
```python
"""
User Manager - Håndterer bruger identifikation
"""
import os
import hashlib
import getpass
from typing import Tuple

class UserManager:
    @staticmethod
    def get_or_create_user() -> str:
        """Få eller opret bruger ID baseret på system"""
        # Kombiner username og computer navn for unik ID
        username = getpass.getuser()
        computer_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
        user_string = f"{username}@{computer_name}"
        
        # Lav hash for privatliv
        user_hash = hashlib.md5(user_string.encode()).hexdigest()[:8]
        return user_hash
    
    @staticmethod
    def get_user_data_dir(user_id: str) -> str:
        """Få bruger data directory navn"""
        return f"user_data_{user_id}"
    
    @staticmethod
    def ensure_user_directory(user_data_dir: str) -> bool:
        """Sikr at bruger directory eksisterer"""
        try:
            if not os.path.exists(user_data_dir):
                os.makedirs(user_data_dir)
            return True
        except Exception as e:
            print(f"Error creating user directory: {e}")
            return False
    
    @staticmethod
    def get_user_info() -> Tuple[str, str]:
        """Få bruger information"""
        username = getpass.getuser()
        computer_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
        return username, computer_name