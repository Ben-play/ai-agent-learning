from .schemas import Message # 绝对导入

def create_response(user_input: str) -> Message:
    return Message(role="assistant", content=f"你说的是：{user_input}")