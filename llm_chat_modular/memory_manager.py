"""
AI Hukommelse system for LLM Chat applikationen
"""
import json
import time
import requests
import threading
from datetime import datetime
from config import Config

class MemoryManager:
    """Håndterer AI hukommelse system"""
    
    def __init__(self, memory_file_path, llm_url):
        self.memory_file = memory_file_path
        self.llm_url = llm_url
        self.user_memory = {}
        self.auto_memory_threshold = Config.DEFAULT_AUTO_MEMORY_THRESHOLD
        self.message_count = 0
        self.auto_memory_enabled = True
        self.timeout_seconds = Config.DEFAULT_TIMEOUT
        self.timeout_enabled = Config.DEFAULT_TIMEOUT_ENABLED
        
        # Callbacks for GUI updates
        self.on_memory_updated = None
        self.on_status_update = None
        
        self.load_user_memory()
    
    def set_callbacks(self, on_memory_updated=None, on_status_update=None):
        """Sæt callback funktioner for GUI opdateringer"""
        self.on_memory_updated = on_memory_updated
        self.on_status_update = on_status_update
    
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
    
    def get_memory_count(self):
        """Få antal minder"""
        return len(self.user_memory)
    
    def get_memory_for_ai(self):
        """Få minder til AI system prompt"""
        if not self.user_memory:
            return ""
        
        memory_summary = "\n\nVigtig information om brugeren (brug til at give bedre svar):\n"
        
        # Få de mest vigtige minder
        sorted_memories = sorted(self.user_memory.items(), 
                               key=lambda x: x[1].get("importance", 0), reverse=True)
        
        for memory_id, memory_data in sorted_memories[:Config.MAX_IMPORTANT_MEMORIES]:
            info = memory_data.get("info", "")
            if info:
                memory_summary += f"- {info}\n"
        
        return memory_summary
    
    def get_sorted_memories(self, sort_by="importance"):
        """Få sorterede minder"""
        if sort_by == "importance":
            return sorted(self.user_memory.items(), 
                         key=lambda x: x[1].get("importance", 0), reverse=True)
        elif sort_by == "date_newest":
            return sorted(self.user_memory.items(), 
                         key=lambda x: x[1].get("created", ""), reverse=True)
        elif sort_by == "date_oldest":
            return sorted(self.user_memory.items(), 
                         key=lambda x: x[1].get("created", ""))
        else:
            return list(self.user_memory.items())
    
    def clear_all_memory(self):
        """Ryd alle minder"""
        self.user_memory = {}
        self.save_user_memory()
        if self.on_memory_updated:
            self.on_memory_updated()
    
    def check_auto_memory_update(self):
        """Tjek om det er tid til automatisk hukommelse opdatering"""
        if not self.auto_memory_enabled:
            return
            
        self.message_count += 1
        
        if self.on_status_update:
            self.on_status_update(f"🤖 Auto-hukommelse: {self.message_count}/{self.auto_memory_threshold}")
        
        if self.message_count >= self.auto_memory_threshold:
            self.message_count = 0
            if self.on_status_update:
                self.on_status_update("🔄 Analyserer samtale...")
            return True
        return False
    
    def force_update_memory(self, conversation_history):
        """Tving hukommelse opdatering nu"""
        if len(conversation_history) < 3:
            return False
        
        if self.on_status_update:
            self.on_status_update("🔄 Opdaterer hukommelse...")
        
        threading.Thread(target=self._auto_update_memory, args=(conversation_history,), daemon=True).start()
        return True
    
    def auto_update_memory(self, conversation_history):
        """Automatisk opdatering af hukommelse"""
        threading.Thread(target=self._auto_update_memory, args=(conversation_history,), daemon=True).start()
    
    def _auto_update_memory(self, conversation_history):
        """Automatisk opdatering af hukommelse (baggrund)"""
        try:
            # Saml seneste beskeder til analyse
            recent_messages = []
            for msg in conversation_history[-4:]:  # Sidste 4 beskeder
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
                "temperature": Config.MEMORY_ANALYSIS_TEMPERATURE,
                "max_tokens": Config.MEMORY_ANALYSIS_MAX_TOKENS,
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
                    new_count = self._process_memory_updates(memory_updates)
                    
                    # Gem og opdater GUI hvis der er nye minder
                    if new_count > 0:
                        self.save_user_memory()
                        if self.on_memory_updated:
                            self.on_memory_updated()
                        if self.on_status_update:
                            self.on_status_update(f"✅ {new_count} nye minder!", temp=True)
                    else:
                        if self.on_status_update:
                            self.on_status_update("🤖 Ingen nye minder denne gang", temp=True)
                    
            except json.JSONDecodeError as e:
                print(f"Auto-hukommelse JSON fejl: {e}")
                if self.on_status_update:
                    self.on_status_update("❌ Hukommelse JSON fejl", temp=True)
                
        except requests.exceptions.Timeout:
            print("Auto-hukommelse timeout")
            if self.on_status_update:
                self.on_status_update("⏱️ Hukommelse timeout", temp=True)
        except requests.exceptions.ConnectionError:
            print("Auto-hukommelse forbindelse fejl")
            if self.on_status_update:
                self.on_status_update("❌ LLM ikke tilgængelig", temp=True)
        except Exception as e:
            print(f"Auto-hukommelse generel fejl: {e}")
            if self.on_status_update:
                self.on_status_update("❌ Hukommelse fejl", temp=True)
    
    def _process_memory_updates(self, memory_updates):
        """Process memory updates og returner antal nye minder"""
        new_count = 0
        if "memories" in memory_updates:
            for memory_data in memory_updates["memories"]:
                importance = memory_data.get("importance", 0)
                if importance >= Config.MIN_IMPORTANCE_SCORE:
                    info = memory_data.get("info", "")
                    
                    if info and not self._memory_exists(info):
                        memory_id = str(int(time.time() * 1000))
                        self.user_memory[memory_id] = {
                            "info": info,
                            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "importance": importance
                        }
                        new_count += 1
        return new_count
    
    def _memory_exists(self, new_info):
        """Tjek om lignende hukommelse allerede eksisterer"""
        new_info_lower = new_info.lower()
        for memory_data in self.user_memory.values():
            existing_info = memory_data.get("info", "").lower()
            # Simpel check for overlap
            if (len(new_info_lower) > Config.MEMORY_OVERLAP_MIN_LENGTH and 
                new_info_lower in existing_info):
                return True
            if (len(existing_info) > Config.MEMORY_OVERLAP_MIN_LENGTH and 
                existing_info in new_info_lower):
                return True
        return False
    
    def set_auto_memory_enabled(self, enabled):
        """Sæt automatisk hukommelse til/fra"""
        self.auto_memory_enabled = enabled
        self.message_count = 0
    
    def set_auto_memory_threshold(self, threshold):
        """Sæt automatisk hukommelse tærskel"""
        self.auto_memory_threshold = threshold
        self.message_count = 0
    
    def set_timeout_settings(self, enabled, seconds):
        """Sæt timeout indstillinger"""
        self.timeout_enabled = enabled
        self.timeout_seconds = seconds