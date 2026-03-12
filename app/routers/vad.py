import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.vad_service import VADService

router = APIRouter()


@router.websocket("/ws/vad/{user_id}")
async def vad_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    vad = VADService()
    audio_buffer = []
    silence_frames = 0
    is_recording = False
    FRAMES_PER_SECOND = 25  # 40ms per chunk
    SILENCE_FRAMES = int(vad.get_silence_threshold() * FRAMES_PER_SECOND)

    try:
        while True:
            data = await websocket.receive_bytes()
            audio_chunk = np.frombuffer(data, dtype=np.float32)

            speech_detected = vad.is_speech(audio_chunk)

            if speech_detected:
                is_recording = True
                silence_frames = 0
                audio_buffer.append(audio_chunk)
                await websocket.send_json({"event": "speech_start"})

            elif is_recording:
                silence_frames += 1
                audio_buffer.append(audio_chunk)

                if silence_frames >= SILENCE_FRAMES:
                    # 说完了
                    full_audio = np.concatenate(audio_buffer)
                    await websocket.send_json({
                        "event": "speech_end",
                        "audio_length": len(full_audio)
                    })
                    audio_buffer.clear()
                    is_recording = False
                    silence_frames = 0

    except WebSocketDisconnect:
        pass
