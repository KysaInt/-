"""
测试多情绪混合功能
"""
import asyncio
import sys
sys.path.insert(0, r"c:\Users\KYSAINT\OneDrive\-\tts\clipboard_tts")

# 导入补丁
import edge_tts_patch
import edge_tts

async def test_emotion_mix():
    """测试多种情绪混合"""
    voice = "zh-CN-XiaoxiaoNeural"
    
    # 测试1: 单一情绪
    print("\n测试1: 单一情绪 - 高兴")
    text1 = '<mstts:express-as style="cheerful" styledegree="1.5">今天天气真好！</mstts:express-as>'
    comm1 = edge_tts.Communicate(text1, voice)
    await comm1.save("test_mix_1_cheerful.mp3")
    print("✓ 生成 test_mix_1_cheerful.mp3")
    
    # 测试2: 双重情绪嵌套
    print("\n测试2: 双重情绪 - 高兴+温柔")
    text2 = '<mstts:express-as style="cheerful" styledegree="1.2"><mstts:express-as style="gentle" styledegree="0.8">今天天气真好！</mstts:express-as></mstts:express-as>'
    comm2 = edge_tts.Communicate(text2, voice)
    await comm2.save("test_mix_2_cheerful_gentle.mp3")
    print("✓ 生成 test_mix_2_cheerful_gentle.mp3")
    
    # 测试3: 三重情绪嵌套
    print("\n测试3: 三重情绪 - 高兴+温柔+友好")
    text3 = '<mstts:express-as style="cheerful" styledegree="1.0"><mstts:express-as style="gentle" styledegree="0.8"><mstts:express-as style="friendly" styledegree="1.2">今天天气真好！</mstts:express-as></mstts:express-as></mstts:express-as>'
    comm3 = edge_tts.Communicate(text3, voice)
    await comm3.save("test_mix_3_multi.mp3")
    print("✓ 生成 test_mix_3_multi.mp3")
    
    print("\n" + "="*60)
    print("测试完成! 请听听效果差异")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_emotion_mix())
