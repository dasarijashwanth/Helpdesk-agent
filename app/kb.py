"""Knowledge base loader + BM25 retrieval over the StyleDesk help articles."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class KnowledgeBase:
    def __init__(self, articles: list[dict]) -> None:
        self.articles = articles
        self._corpus = [tokenize(a["title"] + " " + a["body"]) for a in articles]
        self._bm25 = BM25Okapi(self._corpus)

    @classmethod
    def load(cls, path: Path = DATA_PATH) -> "KnowledgeBase":
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        return cls(payload["articles"])

    def search(self, query: str, top_k: int = 3) -> list[tuple[dict, float]]:
        """Return (article, score) pairs sorted by descending BM25 score."""
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            zip(self.articles, scores), key=lambda pair: pair[1], reverse=True
        )
        return [(article, float(score)) for article, score in ranked[:top_k]]
