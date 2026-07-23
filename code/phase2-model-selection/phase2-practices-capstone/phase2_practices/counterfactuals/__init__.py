"""Deliberately failing demonstrations of unsafe assessment designs."""


class CounterfactualReached(AssertionError):
    """Sentinel proving a counterfactual module reached its intended failure."""


__all__ = ["CounterfactualReached"]
