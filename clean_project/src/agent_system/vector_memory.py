from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

STATE_PATH = Path(".agent_state/chat_memory.jsonl")
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    tokens = [t for t in text.replace("\n", " ").split() if len(t) > 2]
    return tokens[:2048]


def _bow(tokens: List[str]) -> Dict[str, int]:
    bag: Dict[str, int] = {}
    for t in tokens:
        bag[t] = bag.get(t, 0) + 1
    return bag


def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    num = float(sum(a[t] * b[t] for t in common))
    denom_a: float = sum(v * v for v in a.values()) ** 0.5
    denom_b: float = sum(v * v for v in b.values()) ** 0.5
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return num / (denom_a * denom_b)


@dataclass
class MemoryItem:
    text: str
    meta: Dict[str, Any]


class SimpleVectorMemory:
    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        self.items: List[MemoryItem] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    self.items.append(
                        MemoryItem(text=obj.get("text", ""), meta=obj.get("meta", {}))
                    )
        except Exception:
            # If corrupted, start fresh
            self.items = []

    def _append_file(self, item: MemoryItem) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"text": item.text, "meta": item.meta}, ensure_ascii=False) + "\n")

    def add(self, text: str, meta: Dict[str, Any]) -> None:
        if not text:
            return
        item = MemoryItem(text=text, meta=meta)
        self.items.append(item)
        self._append_file(item)

    def query(self, query_text: str, top_k: int = 5) -> List[Tuple[float, MemoryItem]]:
        q_tokens = _tokenize(query_text)
        q_vec = _bow(q_tokens)
        scored: List[Tuple[float, MemoryItem]] = []
        for it in self.items:
            score = _cosine(q_vec, _bow(_tokenize(it.text)))
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]
