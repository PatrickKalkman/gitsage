"""Types for rendering and formatting release notes."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class RenderTemplate:
    """Template configuration for rendering."""

    name: str
    format_type: str  # 'markdown', 'html', 'pdf'
    template_path: str
    variables: Dict[str, Any] = field(default_factory=dict)
    partials: Dict[str, str] = field(default_factory=dict)


@dataclass
class RenderOptions:
    """Options for controlling the rendering process."""

    include_header: bool = True
    include_footer: bool = True
    include_metadata: bool = True
    link_issues: bool = True
    link_commits: bool = True
    emoji_support: bool = True
    syntax_highlighting: bool = True
    custom_css: Optional[str] = None


@dataclass
class RenderedVersion:
    """A single rendered version of the release notes."""

    format_type: str
    content: str
    template_used: str
    generation_date: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedContent:
    """Collection of rendered release notes in various formats."""

    markdown: str
    html: Optional[str] = None
    pdf_path: Optional[str] = None
    versions: Dict[str, RenderedVersion] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_version(self, audience: str, version: RenderedVersion) -> None:
        """Add a new rendered version for a specific audience."""
        self.versions[audience] = version

    def get_supported_formats(self) -> List[str]:
        """Get list of available output formats."""
        formats = ["markdown"]
        if self.html:
            formats.append("html")
        if self.pdf_path:
            formats.append("pdf")
        return formats
