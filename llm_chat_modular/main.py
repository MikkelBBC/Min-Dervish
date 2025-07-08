"""
Hovedapplikation for LLM Chat
Samler alle komponenter og starter applikationen
"""
from gui import LLMChatGUI
from gui_actions import GUIActions

class LLMChatApp(LLMChatGUI, GUIActions):
    """
    Hovedapplikation som kombinerer GUI og Actions
    """
    def __init__(self, llm_url=None):
        # Initialiser GUI komponenter
        super().__init__(llm_url)

def main():
    """Hovedfunktion"""
    print("🚀 Starter Optimeret LLM Chat GUI...")
    print("✨ Nye funktioner:")
    print("  - Modulær arkitektur")
    print("  - Konfigurerbar timeout (10-120 sekunder)")
    print("  - Kan slå timeout helt fra")
    print("  - Automatisk AI hukommelse")
    print("  - Permanent hukommelse på tværs af samtaler")
    print("  - Indstillinger menu (⚙️)")
    print("  - Bruger isolation (sikre samtaler)")
    print("  - Forbedret fejlhåndtering")
    print("  - Lettere at vedligeholde og udvide")
    
    app = LLMChatApp()
    app.run()

if __name__ == "__main__":
    main()