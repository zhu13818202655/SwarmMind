
import requests
import json


def tavily_search(api_token, query, **kwargs):
    """
    使用 Tavily API 进行搜索

    Args:
        api_token: Tavily API Token
        query: 搜索查询
        **kwargs: 可选参数覆盖默认值

    Returns:
        API 响应的 JSON 数据
    """
    url = "https://api.tavily.com/search"

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # 默认参数
    payload = {
        "query": query,
        "auto_parameters": False,
        "topic": "general",
        "search_depth": "basic",
        "chunks_per_source": 3,
        "max_results": 1,
        "time_range": None,
        "start_date": "2025-02-09",
        "end_date": "2025-12-29",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_favicon": False,
        "include_domains": [],
        "exclude_domains": [],
        "country": None,
        "include_usage": False
    }

    # 用传入的参数覆盖默认值
    payload.update(kwargs)

    # 移除值为 None 的字段（可选）
    payload = {k: v for k, v in payload.items() if v is not None}

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()

   
if __name__ == "__main__":
    # 替换为你的实际 API Token
    API_TOKEN = ""

    # 示例调用
    result = tavily_search(
        api_token=API_TOKEN,
        query="who is Leo Messi?",
        max_results=5,  # 覆盖默认值
        include_answer=True  # 覆盖默认值
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
