import requests

# Test om serveren kører
response = requests.get("http://localhost:1234/v1/models")
print(response.json())