import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}
url = "https://entertain.naver.com/ranking"
res = requests.get(url, headers=headers)
with open("test_out.txt", "w", encoding="utf-8") as f:
    f.write(res.text)
