from agent.core import create_response

def test_create_response():
    response = create_response("Hello, how can I assist you today?")
    from agent.schemas import Message
    assert isinstance(response, Message)
    assert "Hello" in response.content