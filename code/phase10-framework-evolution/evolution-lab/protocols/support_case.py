"""Shared synthetic support evidence. No credentials, personal data, or I/O."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Actor:
    tenant: str
    name: str


@dataclass(frozen=True)
class Evidence:
    document: str
    version: int
    locator: str
    text: str


@dataclass(frozen=True)
class Case:
    owner: Actor
    evidence: Evidence


MEI = Actor("support", "mei")
LIN = Actor("support", "lin")
OTHER_MEI = Actor("ops", "mei")
CASES = MappingProxyType({
    "export": Case(MEI, Evidence("EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。")),
    "sync": Case(MEI, Evidence("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。")),
})
