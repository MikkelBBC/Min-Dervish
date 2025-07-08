# LLM Chat GUI - Modulær Version

En avanceret Python GUI applikation til chat med lokale LLM modeller via LM Studio, nu opdelt i modulære komponenter for bedre vedligeholdelse og udvidelse.

## 🆕 Nye Funktioner i Modulær Version

- **Modulær arkitektur** - Koden er opdelt i logiske moduler
- **Forbedret fejlhåndtering** - Bedre error handling og debugging
- **Lettere vedligeholdelse** - Hver komponent har sit eget ansvar
- **Nem udvidelse** - Tilføj nye funktioner uden at ændre eksisterende kode
- **Bedre testbarhed** - Hver modul kan testes isoleret

## 📁 Projektstruktur

```
llm_chat_modular/
├── config.py              # Konfiguration og konstanter
├── user_manager.py        # Bruger håndtering og data mapper
├── session_manager.py     # Chat session håndtering
├── memory_manager.py      # AI hukommelse system
├── audio_manager.py       # TTS og stemme genkendelse
├── llm_client.py          # LLM kommunikation
├── gui.py                 # Hovedgrafisk interface
├── gui_actions.py         # GUI action metoder
├── main.py                # Hovedapplikation
├── requirements.txt       # Python dependencies
└── README.md             # Denne fil
```

## 🛠️ Installation

1. **Klon eller download filerne**
2. **Installer dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Start LM Studio** og load en model
4. **Kør applikationen:**
   ```bash
   python main.py
   ```

## 📋 Modulbeskrivelser

### `config.py`
- Centrale konfigurationer og konstanter
- LLM indstillinger, GUI settings, fil stier
- System prompts og standard værdier

### `user_manager.py`
- Håndterer bruger identifikation
- Opretter og administrerer bruger data mapper
- Sikrer bruger isolation

### `session_manager.py`
- Administrerer chat sessions
- Gemmer og loader samtale historik
- Håndterer system prompts (dansk/engelsk)

### `memory_manager.py`
- AI hukommelse system
- Automatisk analyse af samtaler
- Permanent lagring af bruger information

### `audio_manager.py`
- Text-to-Speech (TTS) funktionalitet
- Stemme genkendelse og input
- Audio device håndtering

### `llm_client.py`
- Kommunikation med LLM via API
- Asynkron besked håndtering
- Timeout og fejl håndtering

### `gui.py`
- Hovedgrafisk interface
- GUI komponent setup
- Event handling og callbacks

### `gui_actions.py`
- Alle GUI action metoder
- Bruger interaktioner
- Display opdateringer

### `main.py`
- Starter applikationen
- Kombinerer alle komponenter
- Entry point for programmet

## ✨ Funktioner

### 🧠 AI Hukommelse
- **Automatisk læring** - AI'en husker automatisk information om dig
- **Permanent lagring** - Minder gemmes mellem samtaler
- **Intelligent analyse** - Kun vigtig information gemmes
- **Konfigurerbar** - Juster hvor ofte hukommelsen opdateres

### 💬 Chat Sessions
- **Multiple samtaler** - Opret og administrer flere samtaler
- **Persistent lagring** - Samtaler gemmes automatisk
- **Bruger isolation** - Hver bruger har sine egne samtaler

### 🔊 Audio Support
- **Text-to-Speech** - AI'en kan oplæse svar
- **Stemme input** - Tal i stedet for at skrive
- **Dansk support** - Understøtter danske stemmer

### ⚙️ Indstillinger
- **Konfigurerbar timeout** - Juster eller deaktiver timeouts
- **Hukommelse indstillinger** - Kontroller automatisk læring
- **Sprog indstillinger** - Vælg dansk eller engelsk svar

### 👤 Bruger System
- **Automatisk identifikation** - Baseret på computer og bruger
- **Data isolation** - Hver bruger har sine egne data
- **Sikkerhed** - Bruger ID'er er hashede for privatliv

## 🎯 Fordele ved Modulær Arkitektur

### For Udviklere
- **Lettere at forstå** - Hver fil har et klart ansvar
- **Nem debugging** - Isoler problemer til specifikke moduler
- **Parallel udvikling** - Flere kan arbejde på forskellige moduler
- **Genbrugelig kode** - Moduler kan bruges i andre projekter

### For Vedligeholdelse
- **Lettere opdateringer** - Ændre kun det relevante modul
- **Bedre testing** - Test hver komponent isoleret
- **Mindre risiko** - Ændringer påvirker kun relaterede dele
- **Bedre dokumentation** - Hver modul kan dokumenteres separat

### For Udvidelse
- **Nye funktioner** - Tilføj nye moduler uden at ændre eksisterende
- **Plugin system** - Nem integration af tredjepartskomponenter
- **Skalering** - Hver komponent kan optimeres uafhængigt
- **Alternative implementeringer** - Udskift moduler med nye versioner

## 🔧 Udvikling

### Tilføjelse af Nye Funktioner
1. **Identificer relevant modul** eller opret nyt modul
2. **Tilføj funktionalitet** i det passende modul
3. **Opdater callbacks** i gui.py hvis nødvendigt
4. **Test isoleret** før integration

### Eksempel: Tilføj Ny Audio Provider
```python
# Opret ny fil: audio_providers/azure_tts.py
class AzureTTSProvider:
    def speak(self, text):
        # Azure TTS implementation
        pass

# Opdater audio_manager.py
from audio_providers.azure_tts import AzureTTSProvider

class AudioManager:
    def __init__(self):
        self.tts_provider = AzureTTSProvider()
```

## 🐛 Debugging

### Log Output
Hvert modul printer relevante debug informationer til konsollen.

### Common Issues
- **LLM forbindelse** - Tjek at LM Studio kører på port 1234
- **Audio fejl** - Installer pyaudio for bedre mikrofon support
- **Memory fejl** - Tjek fil permissions i user_data mapper

## 📈 Performance

### Memory Usage
- Automatisk cleanup af gamle minder
- Begrænsning af samtale historik
- Efficient JSON serialization

### Response Time
- Asynkron LLM kommunikation
- Background processing af hukommelse
- Optimeret GUI opdateringer

## 🛡️ Sikkerhed

- **Bruger isolation** - Data separeres per bruger
- **Hashed user IDs** - Privatliv beskyttelse
- **Local storage** - Ingen data sendes til eksterne servere
- **No API keys** - Bruger kun lokal LLM

## 📞 Support

Ved problemer eller spørgsmål:
1. **Tjek konsol output** for fejlbeskeder
2. **Verificer LM Studio** kører korrekt
3. **Tjek fil permissions** i projektmappen
4. **Prøv at genstarte** både applikation og LM Studio

---

*Modulær LLM Chat GUI - Skalerbar, vedligeholdelig og brugervenlig!* 🚀