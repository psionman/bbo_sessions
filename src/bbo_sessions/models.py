from dataclasses import dataclass
from datetime import date


@dataclass
class Session:
    number: str
    date: date
