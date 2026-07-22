import sys

from agent import create_response


def run():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    msg = create_response("Hello Agent!")
    print(msg)

if __name__ == "__main__":
    run()