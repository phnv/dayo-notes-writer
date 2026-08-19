from typing import Any
from pydantic import BaseModel

class NoteDraft(BaseModel):
    title: str
    body: str
    tags: list[str]
    frontmatter: dict[str, Any]
