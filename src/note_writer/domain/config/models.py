from typing import Any, Optional
from pydantic import BaseModel, Field

class BundleConfig(BaseModel):
    template: str
    prompt: Optional[str] = None
    storage: str
    filename: Optional[str] = None  # supports tokens: {date}, {time}, {datetime}, {slug}
    options: dict[str, Any] = Field(default_factory=dict)


class FrontmatterConfig(BaseModel):
    enabled: bool = True
    format: str = "yaml"
    options: dict[str, Any] = Field(default_factory=dict)

class Config(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)
    templates: dict[str, str] = Field(default_factory=dict)
    prompts: dict[str, str] = Field(default_factory=dict)
    storage: dict[str, str] = Field(default_factory=dict)
    bundles: dict[str, BundleConfig] = Field(default_factory=dict)
    defaults: dict[str, str] = Field(default_factory=dict)
    frontmatter: FrontmatterConfig = Field(default_factory=FrontmatterConfig)
    options: dict[str, Any] = Field(default_factory=dict)
