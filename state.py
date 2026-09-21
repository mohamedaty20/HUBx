# state.py
from dataclasses import dataclass, field
from typing import Literal

Focus = Literal["knowledge", "templates", "both"]
Lang  = Literal["en", "ar"]

@dataclass
class AppState:
    focus: Focus = "both"      # which pipeline the AI concentrates on
    lang:  Lang  = "en"        # UI + output language
    # per-focus enable flags, derived from focus
    @property
    def run_knowledge(self) -> bool:
        return self.focus in ("knowledge", "both")
    @property
    def run_templates(self) -> bool:
        return self.focus in ("templates", "both")

STATE = AppState()
