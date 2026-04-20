from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROFILES_DIR = Path(__file__).parent.parent / "profiles"


@dataclass
class KeywordRule:
    question_keyword: str
    preferred_answers: list[str]
    ratio: float = 1.0  # 0.0–1.0: xác suất áp dụng rule này


@dataclass
class TextRule:
    question_keyword: str
    answers: list[str]  # pool đoạn văn, random pick 1 mỗi lần


@dataclass
class RunConfig:
    form_url: str = ""
    n_submissions: int = 2
    headless: bool = False
    form_language: str = "auto"       # "auto" | "vi" | "en"
    randomization_level: int = 3      # 1 (luôn theo keyword) → 5 (random hoàn toàn)
    rating_direction: str = "positive" # "positive" | "negative" | "neutral"
    delay_min: float = 1.0
    delay_max: float = 3.0
    no_submit: bool = False
    date_start: str = "2020-01-01"    # YYYY-MM-DD
    date_end: str = "2024-12-31"
    keyword_rules: list[KeywordRule] = field(default_factory=list)
    text_rules: list[TextRule] = field(default_factory=list)
    avoid_answers: list[str] = field(default_factory=list)  # global blacklist keywords for all options

    def keyword_apply_prob(self, base_ratio: float) -> float:
        """Tính xác suất áp dụng keyword rule dựa trên randomization_level."""
        # level 1 → giữ nguyên ratio, level 5 → giảm 70%
        factor = 1.0 - (self.randomization_level - 1) * 0.175
        return base_ratio * max(factor, 0.0)


# ── Serialization helpers ────────────────────────────────────────────────────

def _config_to_dict(cfg: RunConfig) -> dict:
    d = asdict(cfg)
    return d


def _config_from_dict(d: dict) -> RunConfig:
    keyword_rules = [KeywordRule(**r) for r in d.pop("keyword_rules", [])]
    text_rules = [TextRule(**r) for r in d.pop("text_rules", [])]
    return RunConfig(**d, keyword_rules=keyword_rules, text_rules=text_rules)


# ── Profile management ────────────────────────────────────────────────────────

def save_profile(config: RunConfig, name: str) -> Path:
    PROFILES_DIR.mkdir(exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    path.write_text(json.dumps(_config_to_dict(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_profile(name: str) -> RunConfig:
    path = PROFILES_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return _config_from_dict(data)


def list_profiles() -> list[str]:
    PROFILES_DIR.mkdir(exist_ok=True)
    return [p.stem for p in sorted(PROFILES_DIR.glob("*.json"))]
