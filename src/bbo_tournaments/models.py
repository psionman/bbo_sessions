from dataclasses import dataclass
from datetime import date


@dataclass
class Tournament:
    number: str
    date: date
