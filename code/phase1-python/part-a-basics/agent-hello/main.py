from agent.core import create_response

def run():
    msg = create_response("Hello, how can I assist you today?")
    print(msg)

if __name__ == "__main__":
    run()