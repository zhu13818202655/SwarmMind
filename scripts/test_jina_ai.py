import requests

def fetch_with_jina(url, api_key):
    """
    使用 Jina AI Reader API 获取网页内容
    """
    # Jina Reader 的基础 URL
    jina_reader_url = "https://r.jina.ai/"

    # 构造完整的请求 URL (将目标 URL 拼接到 Jina 域名后)
    target_url = jina_reader_url + url

    # 设置请求头，包含你的 API Key
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        # 发送 GET 请求
        response = requests.get(target_url, headers=headers, timeout=15)

        # 检查响应状态码
        if response.status_code == 200:
            print(" 请求成功！以下是网页内容：\n")
            print(response.text)
        else:
            print(f" 请求失败，状态码：{response.status_code}")
            print(f"响应内容：{response.text}")

    except requests.exceptions.RequestException as e:
        print(f"网络请求发生异常：{e}")

# https://github.com/intergalacticalvariable/reader 参考
def fetch_local_jina(url, text_type: str = "markdown"):
    # Jina Reader 的基础 URL
    jina_reader_url = "http://127.0.0.1:6125/"

    # 构造完整的请求 URL (将目标 URL 拼接到 Jina 域名后)
    target_url = jina_reader_url + url

    # 设置请求头，包含你的 API Key
    headers = {
        "X-Respond-With": f"{text_type}"
    }

    try:
        # 发送 GET 请求
        response = requests.get(target_url, headers=headers, timeout=15)

        # 检查响应状态码
        if response.status_code == 200:
            print(" 请求成功！以下是网页内容：\n")
            print(response.text)
        else:
            print(f" 请求失败，状态码：{response.status_code}")
            print(f"响应内容：{response.text}")

    except requests.exceptions.RequestException as e:
        print(f"网络请求发生异常：{e}")

if __name__ == "__main__":
    # 1. 替换为你的 Jina AI API Key
    YOUR_API_KEY = "jina_xxx"

    # 2. 目标网页 URL
    TARGET_PAGE_URL = "https://zhuanlan.zhihu.com/p/2025871007580189175"

    # 3. 调用函数
    # fetch_with_jina(TARGET_PAGE_URL, YOUR_API_KEY)
    fetch_local_jina(TARGET_PAGE_URL, text_type="markdown")