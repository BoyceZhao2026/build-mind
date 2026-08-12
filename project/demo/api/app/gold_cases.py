from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml


class GoldCaseRepository:
    def __init__(self, path: Path):
        self.path = path
        self.cases: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self.cases = []
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.cases = data.get("cases", [])

    @staticmethod
    def normalize(text: str) -> str:
        return "".join(text.split()).replace("，", ",").replace("。", "")

    def best_match(self, text: str) -> tuple[dict[str, Any] | None, float]:
        normalized = self.normalize(text)
        best: dict[str, Any] | None = None
        best_score = 0.0
        for case in self.cases:
            candidate = self.normalize(case.get("problem", {}).get("text", ""))
            score = SequenceMatcher(None, normalized, candidate).ratio()
            if score > best_score:
                best, best_score = case, score
        return (best, best_score) if best_score >= 0.72 else (None, best_score)

    def public_cases(self) -> list[dict[str, str]]:
        return [
            {
                "case_id": c.get("case_id", ""),
                "problem_type": c.get("scope", {}).get("problem_type", "unknown"),
                "text": c.get("problem", {}).get("text", ""),
            }
            for c in self.cases
        ]
