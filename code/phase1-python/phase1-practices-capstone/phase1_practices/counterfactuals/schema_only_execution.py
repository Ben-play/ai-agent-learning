from __future__ import annotations

from pydantic import BaseModel


class Increment(BaseModel):
    amount: int


def main() -> None:
    state = {"value": 0}
    Increment.model_validate({"amount": 1})  # validation is not execution
    assert state["value"] == 1, "schema validation did not execute the operation"


if __name__ == "__main__":
    main()
