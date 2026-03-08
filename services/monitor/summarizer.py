"""
AI总结服务 - 支持Anthropic/MiniMax SDK
"""
import os
import anthropic

# API配置
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'sk-cp-wnncftw40-0FXBvMvNkPQeIaJdDQ6iCb5DGT1PlwWY0BfCHsvpruGqrd0RX8B0p8SROBNdHvEjAgAhslgNHXw6pqe6ZQVbCW87MHk5GrGMYArT6BOr2jc4w')
# 正确的base_url!
ANTHROPIC_BASE_URL = 'https://api.minimaxi.com/anthropic'


def summarize_text(text, max_length=500):
    """使用AI总结文本"""
    if not text or len(text.strip()) < 10:
        return "内容太短，无法总结"
    
    # 截取前3000字符
    truncated_text = text[:3000]
    
    prompt = f"""请用简洁的语言总结以下视频字幕内容，要求：
1. 提取核心观点和主题
2. 保留关键数据和信息
3. 总结{max_length}字左右

字幕内容：
{truncated_text}"""

    return summarize_with_anthropic(prompt, max_length)


def summarize_with_anthropic(prompt, max_length=500):
    """使用Anthropic SDK (MiniMax) 总结"""
    try:
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL
        )
        
        message = client.messages.create(
            model="MiniMax-M2.5",
            max_tokens=max_length + 200,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # 处理响应
        for block in message.content:
            if block.type == "text":
                return block.text
            elif block.type == "thinking":
                # 思考过程不需要返回
                continue
        
        return "AI返回内容为空"
        
    except Exception as e:
        error_msg = str(e)
        return f"MiniMax总结失败: {error_msg}"
