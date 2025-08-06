"""
Konfiguration og konstanter for LLM Chat GUI
"""
import os

# LLM Indstillinger
LLM_URL = "http://localhost:1234/v1/chat/completions"
LLM_MODELS_URL = "http://localhost:1234/v1/models"
DEFAULT_TIMEOUT = 45
DEFAULT_MAX_TOKENS = 400
DEFAULT_TEMPERATURE = 0.7
ANALYSIS_TEMPERATURE = 0.1
ANALYSIS_MAX_TOKENS = 300

# GUI Indstillinger
WINDOW_TITLE = "🤖 LLM Chat"
WINDOW_SIZE = "1200x800"
WINDOW_BG_COLOR = "#f0f0f0"
CHAT_FONT = ("Arial", 11)
CHAT_BG_COLOR = "white"
CHAT_FG_COLOR = "black"
MEMORY_DISPLAY_BG = "#f9f9f9"
MEMORY_DISPLAY_FG = "darkblue"

# Memory Indstillinger
AUTO_MEMORY_THRESHOLD = 3
MAX_MEMORY_DISPLAY = 10
MAX_IMPORTANT_MEMORIES = 8
MIN_IMPORTANCE_SCORE = 5
MEMORY_ANALYSIS_MESSAGES = 4

# Session Indstillinger
MAX_CONVERSATION_HISTORY = 12
SESSION_NAME_PREFIX = "Samtale"

# TTS Indstillinger
TTS_RATE = 150
TTS_VOLUME = 0.9
DANISH_VOICE_IDENTIFIERS = ['danish', 'dansk', 'da_dk', 'da-dk']

# Speech Recognition
SPEECH_TIMEOUT = 5
SPEECH_PHRASE_LIMIT = 10
SPEECH_ADJUST_DURATION = 1

# System Prompts
DANISH_PROMPT = """Du er en hjælpsom assistent der svarer på dansk. Hold svarene korte og præcise. 
Du har adgang til information om brugeren som kan hjælpe dig med at give bedre og mere personlige svar."""

ENGLISH_PROMPT = """You are a helpful assistant that always responds in English, even if the user writes in Danish or other languages. 
Keep responses concise and clear. You have access to user information that can help you provide better, more personalized responses."""

# Memory Analysis Prompt Template
MEMORY_ANALYSIS_PROMPT = """Analyser denne samtale og find interessant information om brugeren som jeg skal huske.

SAMTALE:
{conversation}

Find ALLE interessante facts om personen - navn, hobbier, præferencer, job, familie, mål, problemer, etc.

Svar med JSON:
{{
    "memories": [
        {{"info": "konkret fact om personen", "importance": 1-10}}
    ]
}}

Kun vigtig information (importance 5+). Tom liste hvis intet interessant."""

# Fil navne
SESSIONS_FILE = "chat_sessions.pkl"
MEMORY_FILE = "user_memory.json"
USER_DATA_PREFIX = "user_data_"

# GUI Tekster
WELCOME_MESSAGE = "Velkommen! Du er logget ind som bruger {user}.\nAI'en husker automatisk information om dig mellem samtaler.\nCtrl+Enter for at sende besked."
NO_MEMORIES_TEXT = "Ingen minder endnu.\n\nChat med AI'en og den vil automatisk huske interessant information om dig!"
CHAT_CLEARED_WITH_MEMORIES = "Chat ryddet. AI'en husker stadig {count} ting om dig! Start en ny samtale."
CHAT_CLEARED_NO_MEMORIES = "Chat ryddet. Start en ny samtale!"