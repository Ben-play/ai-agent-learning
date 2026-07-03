class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def __repr__(self):
        return f"Message(role={self.role}, content={self.content})"