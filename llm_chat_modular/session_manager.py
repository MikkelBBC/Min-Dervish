"""
Session håndtering for LLM Chat applikationen
"""
import os
import pickle
import time
from datetime import datetime
from config import Config

class SessionManager:
    """Håndterer chat sessions"""
    
    def __init__(self, sessions_file_path, user_id):
        self.sessions_file = sessions_file_path
        self.user_id = user_id
        self.sessions = {}
        self.current_session_id = None
        self.conversation_history = []
        
        # System prompt templates
        self.danish_prompt = Config.DANISH_PROMPT
        self.english_prompt = Config.ENGLISH_PROMPT
        self.current_system_prompt = {
            "role": "system",
            "content": self.danish_prompt
        }
        
        self.load_sessions()
    
    def get_system_prompt_with_memory(self, memory_summary=""):
        """Få system prompt med hukommelse"""
        enhanced_prompt = self.current_system_prompt["content"]
        if memory_summary:
            enhanced_prompt += memory_summary
        return {"role": "system", "content": enhanced_prompt}
    
    def set_english_mode(self, enabled):
        """Sæt engelsk/dansk mode"""
        if enabled:
            self.current_system_prompt["content"] = self.english_prompt
        else:
            self.current_system_prompt["content"] = self.danish_prompt
        
        # Opdater system prompt i aktuel historie
        if (self.conversation_history and 
            self.conversation_history[0]["role"] == "system"):
            self.conversation_history[0] = self.current_system_prompt.copy()
    
    def create_new_session(self, session_name=None):
        """Opret ny session"""
        if not session_name:
            session_name = f"Samtale {len(self.sessions) + 1}"
        
        session_id = f"{self.user_id}_{int(time.time())}"
        self.sessions[session_id] = {
            "name": session_name,
            "history": [self.current_system_prompt.copy()],
            "created": datetime.now(),
            "user": self.user_id
        }
        
        self.current_session_id = session_id
        self.conversation_history = self.sessions[session_id]["history"]
        return session_id, session_name
    
    def load_sessions(self):
        """Load kun denne brugers sessions"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'rb') as f:
                    all_sessions = pickle.load(f)
                    # Filtrer kun denne brugers sessions
                    self.sessions = {k: v for k, v in all_sessions.items() 
                                   if v.get("user") == self.user_id}
            else:
                self.sessions = {}
        except:
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
    
    def save_current_session(self):
        """Gem aktuel session"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.user_id):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
            self.save_sessions()
            return True
        return False
    
    def load_session(self, session_id):
        """Load specifik session"""
        if (session_id in self.sessions and 
            self.sessions[session_id].get("user") == self.user_id):
            self.current_session_id = session_id
            self.conversation_history = self.sessions[session_id]["history"]
            return True
        return False
    
    def delete_session(self, session_id):
        """Slet session"""
        if (session_id in self.sessions and 
            self.sessions[session_id].get("user") == self.user_id):
            session_name = self.sessions[session_id]["name"]
            del self.sessions[session_id]
            
            # Hvis det var den aktuelle session, opret ny
            if self.current_session_id == session_id:
                self.create_new_session()
            
            self.save_sessions()
            return session_name
        return None
    
    def get_user_sessions(self):
        """Få alle bruger sessions sorteret efter dato"""
        user_sessions = {k: v for k, v in self.sessions.items() 
                        if v.get("user") == self.user_id}
        return sorted(user_sessions.items(), 
                     key=lambda x: x[1]["created"], reverse=True)
    
    def get_current_session_name(self):
        """Få navn på aktuel session"""
        if (self.current_session_id and 
            self.current_session_id in self.sessions):
            return self.sessions[self.current_session_id]["name"]
        return "Ny samtale"
    
    def add_message(self, role, content):
        """Tilføj besked til historie"""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_recent_messages(self, count=None):
        """Få seneste beskeder"""
        if count is None:
            count = Config.MAX_CONVERSATION_HISTORY
        return self.conversation_history[-count:]
    
    def clear_conversation(self):
        """Ryd samtale historie"""
        self.conversation_history = [self.current_system_prompt.copy()]
        
        # Opdater session
        if (self.current_session_id and 
            self.current_session_id in self.sessions and
            self.sessions[self.current_session_id].get("user") == self.user_id):
            self.sessions[self.current_session_id]["history"] = self.conversation_history.copy()
    
    def get_message_count_for_session(self, session_id):
        """Få antal beskeder i session"""
        if session_id in self.sessions:
            return len([msg for msg in self.sessions[session_id]["history"] 
                       if msg["role"] == "user"])
        return 0