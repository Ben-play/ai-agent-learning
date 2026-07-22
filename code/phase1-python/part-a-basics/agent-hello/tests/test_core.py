from agent.core import create_response
from agent.schemas import Message


def test_create_response():
    response = create_response("Hello Agent!")
    assert isinstance(response, Message)
    assert response.role == "assistant"
    assert response.content == "你说的是：Hello Agent!"
    assert repr(response) == (
        "Message(role='assistant', content='你说的是：Hello Agent!')"
    )