from typing import Protocol
from pathlib import Path

class Filesystem(Protocol):
    def write_text(self, path: str, content: str) -> None:
        ...
        
    def read_text(self, path: str) -> str:
        ...
        
    def append_text(self, path: str, content: str) -> None:
        ...

class PathlibFilesystem:
    def write_text(self, path: str, content: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        
    def read_text(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")
        
    def append_text(self, path: str, content: str) -> None:
        p = Path(path)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
