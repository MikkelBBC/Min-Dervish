"""
Session Manager - Håndterer chat sessions
"""
import pickle
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
import config

class SessionManager:
    def __init__(self, user_id: str, user_data_dir: str):
        self.user_id = user_id
        self.user_data_dir = user_data_dir
        self.sessions_file = os.path.join(user_data_dir, config.SESSIONS_FILE)
        self.sessions: Dict = {}
        self.current_session_id: Optional[str] = None
        self.conversation_history: List[Dict] = []
        self.load_sessions()
    
    def load_sessions(self):
        """Load kun denne brugers sessions"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'rb') as f:
                    all_sessions = pickle.load(f)
                    # Filtrer kun denne brugers sessions
                    self.sessions = {
                        k: v for k, v in all_sessions.items() 
                        if v.get("user") == self.user_id
                    }
            else:
                self.sessions = {}
        except Exception as e:
            print(f"Error loading sessions: {e}")
            self.sessions = {}
    
    def save_sessions(self):
        """Gem sessions til fil"""
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
    
    def create_session(self, name: str, system_prompt: Dict) -> str:
        """Opret ny session"""
        session_id = f"{self.user_id}_{int(time.time())}"
        self.sessions[session_id] = {
            "name": name,
            "history": [system_prompt.copy()],
            "created": datetime.now(),
            "user": self.user_id
        }
        self.current_session_id = session_id
        self.conversation_history = self.sessions[session_id]["history"]
        return session_id
    
    def load_session(self, session_id: str) -> bool:
        """Load en specifik session"""
        if session_id in self.sessions and self.sessions[session_id].get("user") == self.user_id:
            self.current_session_id = session_id
            self.conversation_history = self.sessions[session_id]["history"]
            return True
        return False
    
    def save_current_session(self) -> bool:
        """Gem aktuel session"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.user_id):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
            self.save_sessions()
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """Slet session"""
        if session_id in self.sessions and self.sessions[session_id].get("user") == self.user_id:
            del self.sessions[session_id]
            if self.current_session_id == session_id:
                self.current_session_id = None
            self.save_sessions()
            return True
        return False
    
    def get_current_session(self) -> Optional[Dict]:
        """Hent aktuel session"""
        if self.current_session_id and self.current_session_id in self.sessions:
            return self.sessions[self.current_session_id]
        return None
    
    def get_user_sessions(self) -> Dict:
        """Hent alle brugerens sessions"""
        return {
            k: v for k, v in self.sessions.items() 
            if v.get("user") == self.user_id
        }
    
    def add_message(self, role: str, content: str):
        """Tilføj besked til conversation history"""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_recent_messages(self, count: int = config.MAX_CONVERSATION_HISTORY) -> List[Dict]:
        """Hent seneste beskeder fra historik"""
        return self.conversation_history[-count:]
    
    def clear_current_history(self, system_prompt: Dict):
        """Ryd aktuel samtale historik"""
        self.conversation_history = [system_prompt.copy()]
        if self.current_session_id:
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Hent session information"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            msg_count = len([msg for msg in session["history"] if msg["role"] == "user"])
            return {
                "name": session["name"],
                "created": session["created"],
                "message_count": msg_count,
                "user": session.get("user")
            }
        return None