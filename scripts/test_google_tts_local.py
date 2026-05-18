"""
本地诊断 Google Cloud Text-to-Speech 是否能用。

用法：
    source venv/bin/activate
    # 在 .env 加一行：GOOGLE_TTS_API_KEY=your_key
    # 或者直接命令行传：
    GOOGLE_TTS_API_KEY=xxx python scripts/test_google_tts_local.py

输出：
    1. raw Google API 调用（不经过我们的 wrapper）—— 如果 raw 就 200，问题在我们 wrapper
       如果 raw 就报错，问题在 key / API enable / IP / quota
    2. 经 multi_tts wrapper 的调用 —— 验证应用层路径
"""
import asyncio
import base64
import os
import sys
import json
import traceback

import httpx

# 让脚本能直接 import 项目
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 加载
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KEY = os.getenv("GOOGLE_TTS_API_KEY", "")


async def raw_test():
    """直打 Google API · 不经我们 wrapper"""
    print("\n========== 步骤 1: 直打 Google API ==========")
    if not KEY:
        print("❌ 没有 GOOGLE_TTS_API_KEY，请先在 .env 里配，或命令行传")
        return False
    print(f"key 前 8 位: {KEY[:8]}…  (长度 {len(KEY)})")

    body = {
        "input": {"text": "Hello world from Speakeasy local test."},
        "voice": {"languageCode": "en-US", "name": "en-US-Neural2-F"},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0},
    }

    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                "https://texttospeech.googleapis.com/v1/text:synthesize",
                params={"key": KEY},
                json=body,
                timeout=15,
            )
        print(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            print("─── 完整响应 body ───")
            print(resp.text[:2000])
            print("────────────────────")
            # 常见错误码翻译
            if resp.status_code == 403:
                print("\n💡 403 通常 = key 没绑 Text-to-Speech API / IP 限制 / billing 未开")
            elif resp.status_code == 400:
                print("\n💡 400 通常 = voice 名 / language 配错；试 Standard 声音 en-US-Standard-C")
            elif resp.status_code == 429:
                print("\n💡 429 = quota 已用尽")
            return False
        data = resp.json()
        audio_b64 = data.get("audioContent", "")
        audio = base64.b64decode(audio_b64) if audio_b64 else b""
        print(f"✓ audioContent 长度 {len(audio_b64)} chars · 解码后音频 {len(audio)} bytes")
        path = "/tmp/google_tts_raw.mp3"
        with open(path, "wb") as f:
            f.write(audio)
        print(f"✓ 写到 {path}（可用 afplay 听一下）")
        return True
    except httpx.ConnectError as e:
        print(f"❌ 网络连不上 Google: {e}")
        print("💡 国内服务器需要科学上网；本地测试也需要")
        return False
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def wrapper_test():
    """经过我们的 _google_tts wrapper"""
    print("\n========== 步骤 2: 经 _google_tts wrapper ==========")
    try:
        from app.services.tts_service import _google_tts
    except Exception as e:
        print(f"❌ import 失败: {e}")
        return False

    try:
        audio, media_type = await _google_tts(
            "Wrapper test from Speakeasy.",
            voice="en-US-JennyNeural",
            speed="+20%",
        )
        print(f"✓ {len(audio)} bytes · {media_type}")
        path = "/tmp/google_tts_wrapper.mp3"
        with open(path, "wb") as f:
            f.write(audio)
        print(f"✓ 写到 {path}")
        return True
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def multi_tts_test():
    """经过 multi_tts (有 cache + 降级)"""
    print("\n========== 步骤 3: 经 multi_tts(provider='google') ==========")
    try:
        from app.services.tts_service import multi_tts
    except Exception as e:
        print(f"❌ import 失败: {e}")
        return False

    try:
        audio, media_type, _meta = await multi_tts(
            "Multi-tts dispatch test.",
            provider="google",
            voice="jenny",
            speed="+0%",
        )
        print(f"✓ {len(audio)} bytes · {media_type}")
        path = "/tmp/google_tts_multi.mp3"
        with open(path, "wb") as f:
            f.write(audio)
        print(f"✓ 写到 {path}")
        return True
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def main():
    ok1 = await raw_test()
    if not ok1:
        print("\n=> raw 就失败，停在这里。修好 key/API/IP/billing 再继续。")
        return
    ok2 = await wrapper_test()
    if not ok2:
        print("\n=> raw OK 但 wrapper fail —— 问题在我们 _google_tts，提示具体错误已打。")
        return
    ok3 = await multi_tts_test()
    if not ok3:
        print("\n=> wrapper OK 但 multi_tts fail —— 问题在 dispatch / cache 逻辑。")
        return
    print("\n✅ 三步全过。线上失败如复现不出来，说明 VPS 上 env 没注入 / IP 限制只限本地。")


if __name__ == "__main__":
    asyncio.run(main())
