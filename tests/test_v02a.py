import asyncio
import httpx

BASE = "http://localhost:8000"


async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=30, trust_env=False) as c:
        # 根路由
        r = await c.get("/")
        assert r.status_code == 200, f"GET / failed: {r.status_code}"

        # chat 含 user_id
        r = await c.post("/chat", json={"user_id": "t", "session_id": "ts", "message": "hi", "history": []})
        assert r.status_code == 200 and "reply" in r.json(), f"POST /chat failed: {r.text}"

        # chat 无 user_id（向后兼容）
        r = await c.post("/chat", json={"message": "hi", "history": []})
        assert r.status_code == 200, f"POST /chat (no uid) failed: {r.status_code}"

        # stream
        chunks = []
        async with c.stream("POST", "/chat/stream",
                json={"user_id": "t", "session_id": "ts2", "message": "say hi", "history": []}) as r:
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    chunks.append(line)
        assert any("done" in l for l in chunks), f"stream 无 done 事件: {chunks}"

        # stt（无 Key → 降级）
        r = await c.post("/stt", files={"audio": ("t.webm", b"\x00" * 100, "audio/webm")})
        assert r.status_code in (200, 503), f"POST /stt unexpected: {r.status_code}"

        # tts
        r = await c.post("/tts", json={"text": "hello"})
        assert r.status_code == 200, f"POST /tts failed: {r.status_code}"
        assert "audio" in r.headers.get("content-type", ""), f"TTS wrong content-type: {r.headers}"

        # history（含分页字段）
        r = await c.get("/history/t")
        d = r.json()
        assert "sessions" in d and "total" in d and "limit" in d, f"history missing fields: {d}"

        # debug
        d = (await c.get("/debug/status")).json()
        for f in ["db", "stt_available", "tts_available"]:
            assert f in d, f"debug 缺字段: {f}"

        print("✅ Step 12 完成 - 全部测试通过")


asyncio.run(run())
