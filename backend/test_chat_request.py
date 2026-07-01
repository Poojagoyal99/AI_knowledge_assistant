import requests
import urllib.parse

query = 'what this pdf is about Pooja_Goyal_handwritten.pdf'
url = 'http://127.0.0.1:8000/api/chat/?query=' + urllib.parse.quote(query)
print('URL:', url)
res = requests.get(url)
print('status:', res.status_code)
print('text:', res.text)
try:
    print('json:', res.json())
except Exception as exc:
    print('json error:', exc)