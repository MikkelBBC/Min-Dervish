"""
Konfiguration og konstanter for LLM Chat applikationen
"""
import os

class Config:
    """Applikations konfiguration"""
    
    # LLM indstillinger
    DEFAULT_LLM_URL = "http://localhost:1234/v1/chat/completions"
    DEFAULT_TIMEOUT = 45
    DEFAULT_TIMEOUT_ENABLED = True
    
    # AI Hukommelse indstillinger
    DEFAULT_AUTO_MEMORY_THRESHOLD = 3
    MAX_CONVERSATION_HISTORY = 12
    MAX_MEMORY_DISPLAY = 10
    MAX_IMPORTANT_MEMORIES = 8
    
    # TTS indstillinger
    TTS_RATE = 150
    TTS_VOLUME = 0.9
    
    # GUI indstillinger
    WINDOW_SIZE = "1200x800"
    WINDOW_BG = "#f0f0f0"
    
    # Fil og mappe navne
    SESSIONS_FILE = "chat_sessions.pkl"
    MEMORY_FILE = "user_memory.json"
    USER_DATA_PREFIX = "user_data_"
    
    # System prompts
    DANISH_PROMPT = """Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise. 
    Du har adgang til information om brugeren som kan hjælpe dig med at give bedre og mere personlige svar."""
    
    ENGLISH_PROMPT = """You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. 
    Keep responses concise and clear. You have access to user information that can help you provide better, more personalized responses."""
    
    # LLM request indstillinger
    LLM_TEMPERATURE = 0.7
    LLM_MAX_TOKENS = 400
    MEMORY_ANALYSIS_TEMPERATURE = 0.1
    MEMORY_ANALYSIS_MAX_TOKENS = 300
    
    # Hukommelse indstillinger
    MIN_IMPORTANCE_SCORE = 5
    MEMORY_OVERLAP_MIN_LENGTH = 10
    
    @staticmethod
    def get_user_data_dir(user_id):
        """Få bruger data mappe"""
        return f"{Config.USER_DATA_PREFIX}{user_id}"
    
    @staticmethod
    def get_sessions_file_path(user_data_dir):
        """Få sessions fil sti"""
        return os.path.join(user_data_dir, Config.SESSIONS_FILE)
    
    @staticmethod
    def get_memory_file_path(user_data_dir):
        """Få memory fil sti"""
        return os.path.join(user_data_dir, Config.MEMORY_FILE)