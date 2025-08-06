"""
LLM Client - Håndterer al kommunikation med Language Model
"""
import requests
import json
from typing import Dict, List, Optional, Tuple
import config

class LLMClient:
    def __init__(self, url: str = config.LLM_URL):
        self.url = url
        self.models_url = config.LLM_MODELS_URL
        self.timeout_enabled = True
        self.timeout_seconds = config.DEFAULT_TIMEOUT
        
    def test_connection(self) -> Tuple[bool, str]:
        """Test LLM forbindelse"""
        try:
            response = requests.get(self.models_url, timeout=3)
            if response.status_code == 200:
                models = response.json()
                model_count = len(models.get('data', []))
                return True, f"✅ LLM forbundet ({model_count} modeller)"
            return False, f"❌ LLM fejl: HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "❌ LM Studio ikke startet"
        except Exception as e:
            return False, f"❌ Forbindelsesfejl: {str(e)[:20]}"
    
    def send_message(self, 
                    messages: List[Dict], 
                    temperature: float = config.DEFAULT_TEMPERATURE,
                    max_tokens: int = config.DEFAULT_MAX_TOKENS,
                    stream: bool = False) -> Dict:
        """Send besked til LLM"""
        headers = {"Content-Type": "application/json"}
        data = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        timeout = self.timeout_seconds if self.timeout_enabled else None
        response = requests.post(self.url, json=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    def extract_response(self, result: Dict) -> str:
        """Udtræk svar fra LLM resultat"""
        return result['choices'][0]['message']['content']
    
    def analyze_for_memory(self, conversation_text: str) -> Optional[Dict]:
        """Analyser samtale for at finde minder"""
        prompt = config.MEMORY_ANALYSIS_PROMPT.format(conversation=conversation_text)
        
        try:
            result = self.send_message(
                messages=[{"role": "user", "content": prompt}],
                temperature=config.ANALYSIS_TEMPERATURE,
                max_tokens=config.ANALYSIS_MAX_TOKENS
            )
            
            response = self.extract_response(result).strip()
            
            # Parse JSON response
            response = response.replace('```json', '').replace('```', '').strip()
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
                
        except (json.JSONDecodeError, requests.exceptions.RequestException) as e:
            print(f"Memory analysis error: {e}")
            return None
        
        return None
    
    def set_timeout(self, enabled: bool, seconds: int = None):
        """Opdater timeout indstillinger"""
        self.timeout_enabled = enabled
        if seconds is not None:
            self.timeout_seconds = seconds