"""
Bruger håndtering for LLM Chat applikationen
"""
import os
import hashlib
import getpass
from config import Config

class UserManager:
    """Håndterer bruger identifikation og data mapper"""
    
    def __init__(self):
        self.current_user = self.get_or_create_user()
        self.user_data_dir = Config.get_user_data_dir(self.current_user)
        self.ensure_user_directory()
    
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
    
    def get_user_id(self):
        """Få bruger ID"""
        return self.current_user
    
    def get_user_data_directory(self):
        """Få bruger data mappe"""
        return self.user_data_dir
    
    def get_sessions_file_path(self):
        """Få sessions fil sti"""
        return Config.get_sessions_file_path(self.user_data_dir)
    
    def get_memory_file_path(self):
        """Få memory fil sti"""
        return Config.get_memory_file_path(self.user_data_dir)