"""
解决edge-tts不支持SSML情绪标签的方案

方案: 直接修改mkssml函数,添加xmlns:mstts命名空间支持
同时修改Communicate的__init__,在转义前提取并保护SSML标签
"""
import edge_tts
from edge_tts import communicate
from xml.sax.saxutils import escape
import re

# 保存原始mkssml
_original_mkssml = communicate.mkssml

def patched_mkssml(tc, escaped_text):
    """修改后的mkssml,添加mstts命名空间"""
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")
    
    # 添加mstts命名空间声明
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
        "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )

# 保存原始Communicate.__init__
_original_communicate_init = communicate.Communicate.__init__

def patched_communicate_init(self, text, voice, *args, **kwargs):
    """
    修改Communicate初始化,在文本转义前提取SSML标签
    """
    # 保存原始文本用于检查
    original_text = text
    
    # 检查是否包含express-as标签
    if '<mstts:express-as' in text and '</mstts:express-as>' in text:
        # 提取标签和内容
        pattern = r'<mstts:express-as\s+([^>]+)>(.*?)</mstts:express-as>'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            attrs = match.group(1)
            inner_text = match.group(2).strip()
            
            # 创建一个标记,让我们能在转义后识别
            # 使用Unicode字符作为标记(不会被转义)
            marker_start = "\u200B__EXPR_START__"  # 零宽空格 + 标记
            marker_attrs = f"\u200B__ATTRS__{attrs}__"
            marker_end = "\u200B__EXPR_END__"
            
            # 替换文本
            text = f"{marker_start}{marker_attrs}{inner_text}{marker_end}"
    
    # 调用原始__init__
    _original_communicate_init(self, text, voice, *args, **kwargs)

# 再包装一层,在split_text之后处理
_original_split = communicate.split_text_by_byte_length

def patched_split(text, max_len):
    result = _original_split(text, max_len)
    
    # 在每个chunk中还原SSML标签
    processed = []
    for chunk in result:
        # 处理bytes和str
        if isinstance(chunk, bytes):
            chunk_str = chunk.decode('utf-8')
        else:
            chunk_str = chunk
            
        if '\u200B__EXPR_START__' in chunk_str:
            # 提取属性
            attrs_match = re.search(r'\u200B__ATTRS__(.+?)__', chunk_str)
            if attrs_match:
                attrs = attrs_match.group(1)
                # 移除标记
                chunk_str = chunk_str.replace('\u200B__EXPR_START__', '')
                chunk_str = chunk_str.replace(f'\u200B__ATTRS__{attrs}__', '')
                chunk_str = chunk_str.replace('\u200B__EXPR_END__', '')
                # 添加SSML标签
                chunk_str = f"<mstts:express-as {attrs}>{chunk_str}</mstts:express-as>"
        
        # 保持原类型
        if isinstance(chunk, bytes):
            processed.append(chunk_str.encode('utf-8'))
        else:
            processed.append(chunk_str)
    
    return processed

# 应用所有补丁
communicate.mkssml = patched_mkssml
communicate.Communicate.__init__ = patched_communicate_init  
communicate.split_text_by_byte_length = patched_split

print("✓ edge-tts高级补丁已应用")
print("  - mkssml: 添加mstts命名空间")
print("  - Communicate.__init__: 保护SSML标签")
print("  - split_text: 还原SSML标签")
