from pydantic import BaseModel


# 单条消息
class Message(BaseModel):
    role: str       # "user" 或 "assistant"
    content: str    # 消息内容


# 对话请求
class ChatRequest(BaseModel):
    session_id: str           # 会话唯一ID，由调用方生成 UUID
    message: str              # 用户当前输入
    history: list[Message]    # 历史消息列表，由调用方维护和传入


# 对话响应
class ChatResponse(BaseModel):
    reply: str          # AI 回复内容
    session_id: str     # 回传 session_id
    request_id: str = ""  # 本次请求唯一追踪 ID


# 结束对话请求
class EndSessionRequest(BaseModel):
    session_id: str
    history: list[Message]    # 完整对话历史


# 今日一句响应
class SummaryResponse(BaseModel):
    tip: str            # 今日一句内容
    session_id: str


# 统一错误响应
class ErrorResponse(BaseModel):
    error: str          # 错误描述
    session_id: str = ""  # 如果有 session_id 则回传
