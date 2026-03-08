import requests

def google_search(query, api_key, cx, num=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': api_key,
        'cx': cx,
        'num': num
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        for item in items:
            print(f"标题: {item['title']}")
            print(f"链接: {item['link']}")
            print(f"摘要: {item.get('snippet')}\n")
    else:
        print(f"请求失败，状态码: {response.status_code}")
        print(response.text)

# 使用示例
API_KEY = "7723daaff2a2155b7882d8d8cee6fbb444e07d8c"
CX = "114347988173001436116"
google_search("Python教程", API_KEY, CX)