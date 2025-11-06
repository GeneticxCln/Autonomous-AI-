from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_FILE = Path(".agent_state/todos.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Todo:
    id: int
    title: str
    status: str = "open"  # open|done
    priority: int = 3      # 1..5
    created_at: str = datetime.now(UTC).isoformat()
    completed_at: Optional[str] = None


class SimpleTodoStore:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.items: List[Todo] = []
        self._load()
        self._next_id = max([t.id for t in self.items], default=0) + 1

    def _load(self):
        if not self.path.exists():
            self.items = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [Todo(**obj) for obj in data]
        except Exception:
            self.items = []

    def _save(self):
        data = [asdict(t) for t in self.items]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, title: str, priority: int = 3) -> Todo:
        todo = Todo(id=self._next_id, title=title.strip(), priority=max(1, min(5, int(priority))))
        self._next_id += 1
        self.items.append(todo)
        self._save()
        return todo

    def list(self, include_done: bool = False) -> List[Todo]:
        return [t for t in self.items if include_done or t.status != "done"]

    def done(self, todo_id: int) -> bool:
        for t in self.items:
            if t.id == todo_id:
                t.status = "done"
                t.completed_at = datetime.now(UTC).isoformat()
                self._save()
                return True
        return False

    def clear(self, include_open: bool = False) -> int:
        if include_open:
            n = len(self.items)
            self.items = []
        else:
            before = len(self.items)
            self.items = [t for t in self.items if t.status != "done"]
            n = before - len(self.items)
        self._save()
        return n