"""
File Handler - Utility funktioner for fil operationer
"""
import json
import pickle
from typing import Any, Optional

class FileHandler:
    @staticmethod
    def save_json(filepath: str, data: dict, ensure_ascii: bool = False) -> bool:
        """Gem data som JSON fil"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=2)
            return True
        except Exception as e:
            print(f"Error saving JSON: {e}")
            return False
    
    @staticmethod
    def load_json(filepath: str) -> Optional[dict]:
        """Load data fra JSON fil"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return None
    
    @staticmethod
    def save_pickle(filepath: str, data: Any) -> bool:
        """Gem data som pickle fil"""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            print(f"Error saving pickle: {e}")
            return False
    
    @staticmethod
    def load_pickle(filepath: str) -> Optional[Any]:
        """Load data fra pickle fil"""
        try:
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error loading pickle: {e}")
            return None