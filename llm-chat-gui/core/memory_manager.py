"""
Memory Manager - Håndterer AI hukommelse system
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import config

class MemoryManager:
    def __init__(self, user_id: str, user_data_dir: str):
        self.user_id = user_id
        self.user_data_dir = user_data_dir
        self.memory_file = os.path.join(user_data_dir, config.MEMORY_FILE)
        self.user_memory: Dict = {}
        self.auto_memory_threshold = config.AUTO_MEMORY_THRESHOLD
        self.message_count = 0
        self.load_memory()
        
    def load_memory(self):
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
    
    def save_memory(self):
        """Gem bruger hukommelse til fil"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fejl ved gemning af hukommelse: {e}")
    
    def add_memory(self, info: str, importance: int) -> bool:
        """Tilføj ny hukommelse hvis den ikke eksisterer"""
        if not self._memory_exists(info) and importance >= config.MIN_IMPORTANCE_SCORE:
            memory_id = str(int(time.time() * 1000))
            self.user_memory[memory_id] = {
                "info": info,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "importance": importance
            }
            self.save_memory()
            return True
        return False
    
    def _memory_exists(self, new_info: str) -> bool:
        """Tjek om lignende hukommelse allerede eksisterer"""
        new_info_lower = new_info.lower()
        for memory_data in self.user_memory.values():
            existing_info = memory_data.get("info", "").lower()
            # Simpel check for overlap
            if len(new_info_lower) > 10 and new_info_lower in existing_info:
                return True
            if len(existing_info) > 10 and existing_info in new_info_lower:
                return True
        return False
    
    def process_memory_updates(self, memory_data: Dict) -> int:
        """Process memory updates fra AI analyse"""
        new_count = 0
        if memory_data and "memories" in memory_data:
            for memory_item in memory_data["memories"]:
                importance = memory_item.get("importance", 0)
                info = memory_item.get("info", "")
                
                if info and self.add_memory(info, importance):
                    new_count += 1
        
        return new_count
    
    def get_memories_for_prompt(self, max_count: int = config.MAX_IMPORTANT_MEMORIES) -> str:
        """Få minder formateret til AI prompt"""
        if not self.user_memory:
            return ""
        
        memory_summary = "\n\nVigtig information om brugeren (brug til at give bedre svar):\n"
        sorted_memories = sorted(
            self.user_memory.items(), 
            key=lambda x: x[1].get("importance", 0), 
            reverse=True
        )
        
        for memory_id, memory_data in sorted_memories[:max_count]:
            info = memory_data.get("info", "")
            if info:
                memory_summary += f"- {info}\n"
        
        return memory_summary
    
    def get_sorted_memories(self, sort_by: str = "importance") -> List[Tuple[str, Dict]]:
        """Hent sorterede minder"""
        if sort_by == "importance":
            return sorted(
                self.user_memory.items(), 
                key=lambda x: x[1].get("importance", 0), 
                reverse=True
            )
        elif sort_by == "date_newest":
            return sorted(
                self.user_memory.items(), 
                key=lambda x: x[1].get("created", ""), 
                reverse=True
            )
        else:  # date_oldest
            return sorted(
                self.user_memory.items(), 
                key=lambda x: x[1].get("created", "")
            )
    
    def get_memory_count(self) -> int:
        """Få antal minder"""
        return len(self.user_memory)
    
    def clear_all_memories(self):
        """Ryd alle minder"""
        self.user_memory = {}
        self.save_memory()
    
    def increment_message_count(self) -> bool:
        """Increment message counter og returner om threshold er nået"""
        self.message_count += 1
        if self.message_count >= self.auto_memory_threshold:
            self.message_count = 0
            return True
        return False
    
    def reset_message_count(self):
        """Reset message counter"""
        self.message_count = 0
    
    def set_threshold(self, threshold: int):
        """Set auto memory threshold"""
        self.auto_memory_threshold = threshold
        self.reset_message_count()