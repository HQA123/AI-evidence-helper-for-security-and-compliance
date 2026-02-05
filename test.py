
import requests
url = "http://localhost/v1/workflows/ef419c81-03af-4e66-88b7-829106cb3ea6/run"
api_key = "app-EcNwTuK7C7O76Hr9VGbuk2P3"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
payload = {
    "inputs": {
        "query": "这是test_file.png证据",
    },
    "user":"aaa",
    "response_mode":"blocking"
}
result = requests.post(url, headers=headers, json=payload,verify=True)
print(result.json())

