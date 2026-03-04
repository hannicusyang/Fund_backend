"""
AI总结服务
"""
import os
import json

# API配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')


def summarize_text(text, max_length=500):
    """使用AI总结文本"""
    if not text or len(text.strip()) < 10:
        return "内容太短，无法总结"
    
    if not OPENAI_API_KEY:
        # 如果没有API Key，返回原文摘要
        return f"[无AI API，请配置OPENAI_API_KEY] {text[:200]}..."
    
    # TODO: 实现真正的AI总结
    # 这里先用简单截取作为占位
    try:
        import requests
        
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # 截取前2000字符
        truncated_text = text[:2000]
        
        prompt = f"""请用简洁的语言总结以下视频字幕内容，要求：
1. 提取核心观点
2. 保留关键数据
3. 总结时间约{max_length}字

字幕内容：
{truncated_text}"""

        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 800
        }
        
        response = requests.post(
            f'{OPENAI_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result['choices'][0]['message']['content']
            return summary
        else:
            return f"AI总结失败: {response.status_code}"
            
    except Exception as e:
        return f"总结失败: {str(e)}"
