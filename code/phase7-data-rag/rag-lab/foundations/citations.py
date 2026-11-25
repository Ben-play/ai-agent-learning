"""L61: index fixed local sources and reopen their citations through the shared store."""

import json
import runpy
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


CORE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "lab.py"))
LabChunk, Query, EvidenceStore, open_demo = (
    CORE[name] for name in ("Chunk", "Query", "EvidenceStore", "open_demo")
)
FIXTURES = Path(__file__).resolve().with_name("fixtures")


@dataclass(frozen=True)
class SourceFile:
    kind: str
    basename: str
    original: str | None = None  # Only the PDF uses a separate extraction fixture.


# These manifests model trusted publication metadata, not request-supplied paths.
WORKED_CURRENT = (("dispatch", 2), ("office", 4), ("guide", 1))
TRANSFER_INITIAL = (("returns", 3), ("pickup", 1))
TRANSFER_CURRENT = (("returns", 4), ("pickup", 1))
SOURCES = {
    ("dispatch", 2): SourceFile("pdf-page-fixture", "dispatch-v2.pages.json", "dispatch-v2.pdf"),
    ("office", 4): SourceFile("html-paragraph", "office-v4.html"),
    ("guide", 1): SourceFile("markdown-paragraph", "guide-v1.md"),
    ("returns", 3): SourceFile("markdown-paragraph", "returns-v3.md"),
    ("returns", 4): SourceFile("markdown-paragraph", "returns-v4.md"),
    ("pickup", 1): SourceFile("markdown-paragraph", "pickup-v1.md"),
}
TERMS = ("cold-room", "weekday", "周三", "纸质登记", "蓝色标签", "晚班", "归还", "领取台", "发放标签", "附录")
NO_EVIDENCE = "没有可用证据，无法回答。"


@dataclass(frozen=True)
class Citation:
    doc_id: str
    version: int
    locator: str

    @property
    def key(self) -> tuple[str, int, str]:
        return self.doc_id, self.version, self.locator


@dataclass(frozen=True)
class HostScope:
    """Trusted host identity, never built from the question or citation."""

    tenant: str
    user: str


@dataclass(frozen=True)
class Answer:
    scope: HostScope
    text: str
    citation: Citation | None = None


@dataclass(frozen=True)
class Chunk:
    citation: Citation
    text: str


@dataclass(frozen=True)
class Resolution:
    status: str
    chunk: Chunk | None = None
    source_file: str | None = None  # A manifest basename for display, not a link.


class MainParagraphs(HTMLParser):
    """Only for the supplied well-formed fixture: main > p[id] with inline markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.anchor = None
        self.parts = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.in_main = True
        elif self.in_main and tag == "p":
            self.anchor = dict(attrs).get("id")
            self.parts = []

    def handle_data(self, data):
        if self.anchor is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.anchor is not None:
            text = " ".join("".join(self.parts).split())
            self.paragraphs.append((f"paragraph:{self.anchor}", text))
            self.anchor = None
        elif tag == "main":
            self.in_main = False


def load_chunks(doc_id: str, version: int) -> tuple[Chunk, ...]:
    """One chunk per fixed-source page or paragraph; locate before chunking."""
    source = SOURCES[(doc_id, version)]
    text = (FIXTURES / source.basename).read_text(encoding="utf-8")
    if source.kind == "pdf-page-fixture":
        units = [(f"page:{entry['page']}", entry["text"]) for entry in json.loads(text)]
    elif source.kind == "html-paragraph":
        parser = MainParagraphs()
        parser.feed(text)
        parser.close()
        units = parser.paragraphs
    elif source.kind == "markdown-paragraph":  # These fixtures separate prose blocks by blank lines.
        paragraphs = [block.strip() for block in text.strip().split("\n\n")
                      if block.strip() and not block.lstrip().startswith("#")]
        units = [(f"paragraph:{n}", body) for n, body in enumerate(paragraphs, 1)]
    else:
        raise ValueError(f"unsupported fixture format: {source.kind}")
    if not units or len({locator for locator, _ in units}) != len(units):
        raise ValueError(f"missing or ambiguous locators: {doc_id} v{version}")
    if any(not body.strip() for _, body in units):
        raise ValueError(f"empty source unit: {doc_id} v{version}")
    return tuple(Chunk(Citation(doc_id, version, locator), body) for locator, body in units)


class Catalogue:
    """Trusted current manifest for one tenant; this resolver does not grant access."""

    def __init__(self, tenant: str, current: tuple[tuple[str, int], ...]):
        self.tenant = tenant
        self._versions = dict(current)
        if len(self._versions) != len(current):
            raise ValueError("a document cannot have two current editions")
        if any((doc_id, version) not in SOURCES for doc_id, version in current):
            raise ValueError("current source is not in the trusted manifest")

    def resolve(self, citation: Citation) -> Resolution:
        if citation.doc_id not in self._versions:
            return Resolution("unknown_document")
        if citation.version != self._versions[citation.doc_id]:
            return Resolution("version_mismatch")
        source = SOURCES[(citation.doc_id, citation.version)]
        if source.original and not (FIXTURES / source.original).is_file():
            return Resolution("missing_source")
        try:
            for chunk in load_chunks(citation.doc_id, citation.version):
                if chunk.citation == citation:
                    return Resolution("ok", chunk, source.original or source.basename)
        except FileNotFoundError:
            return Resolution("missing_source")
        return Resolution("unknown_locator")

    def seed_rows(self, grants: dict[str, tuple[str, ...]]) -> Iterator[tuple[str, LabChunk, tuple[str, ...]]]:
        """Import every source unit. Only the host supplies the publication and grants."""
        for doc_id, version in self._versions.items():
            for chunk in index_chunks(doc_id, version):
                yield self.tenant, chunk, grants[doc_id]


def index_chunks(doc_id: str, version: int) -> tuple[LabChunk, ...]:
    """Keep the exact original unit and location; use toy lexical terms, not embeddings."""
    return tuple(
        LabChunk(*chunk.citation.key, doc_id, chunk.text,
                 tuple(term for term in TERMS if term in chunk.text.casefold()), (0.0, 0.0, 0.0))
        for chunk in load_chunks(doc_id, version)
    )


def _current_original(db: EvidenceStore, catalogue: Catalogue, scope: HostScope,
                      citation: Citation, quote: str) -> Resolution:
    # Check the exact key under the same host scope before reopening a manifest file.
    if scope.tenant != catalogue.tenant or type(citation.version) is not int:
        return Resolution("unavailable")
    current = db.source(scope.tenant, scope.user, citation.key)
    if current is None or current.text != quote:
        return Resolution("unavailable")
    original = catalogue.resolve(citation)
    if original.chunk is None or original.chunk.text != current.text:
        return Resolution("unavailable")
    return original


def answer(db: EvidenceStore, catalogue: Catalogue, scope: HostScope, query: Query) -> Answer:
    """Quote only a verified top hit carrying every requested tag in this fixture."""
    required = frozenset(query.terms)
    if scope.tenant == catalogue.tenant and required:
        hits = db.search(scope.tenant, scope.user, query, mode="lexical", k=1)
        if hits:
            hit = hits[0].chunk
            if required.issubset(hit.terms):
                citation = Citation(*hit.key)
                original = _current_original(db, catalogue, scope, citation, hit.text)
                if original.chunk is not None:
                    return Answer(scope, hit.text, citation)
    return Answer(scope, NO_EVIDENCE)


def reopen(db: EvidenceStore, catalogue: Catalogue, scope: HostScope, reply: Answer) -> Resolution:
    """Recheck a saved answer in its original scope; don't expose failure reasons."""
    if reply.scope != scope or reply.citation is None:
        return Resolution("unavailable")
    return _current_original(db, catalogue, scope, reply.citation, reply.text)
