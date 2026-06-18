"""
Evidence Package Generator

Creates comprehensive evidence packages for investigations
with full citation, hashing, and export capabilities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

from nciia.models import Evidence, EvidenceItem, Persona, Signal, Case

logger = structlog.get_logger(__name__)


@dataclass
class Citation:
    """A source citation."""
    
    id: str
    source_type: str
    source_name: str
    url: Optional[str]
    accessed_at: datetime
    content_hash: str


@dataclass
class ExportResult:
    """Result of evidence export."""
    
    format: str
    file_path: Optional[str]
    content: Optional[str]
    size_bytes: int
    item_count: int
    hash: str
    timestamp: datetime


class EvidencePackager:
    """
    Creates and exports evidence packages.
    
    Features:
    - Content hashing for integrity
    - Source citations
    - Multiple export formats
    - Timeline generation
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./evidence_export")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_package(
        self,
        case: Case,
        personas: list[Persona],
        signals: list[Signal],
        analyst: str = "system",
    ) -> Evidence:
        """
        Create a complete evidence package.
        
        Args:
            case: The investigation case
            personas: Related personas
            signals: Collected signals
            analyst: Creating analyst ID
            
        Returns:
            Complete Evidence package
        """
        package = Evidence(
            case_id=case.id,
            created_by=analyst,
            title=f"Evidence Package: {case.name}",
            description=case.description,
        )
        
        # Add persona items
        for persona in personas:
            item = EvidenceItem(
                evidence_type="persona",
                content=json.dumps(persona.model_dump(), default=str),
                source_type="reconstruction",
                source_reference=str(persona.id),
            )
            package.items.append(item)
        
        # Add signal items
        for signal in signals:
            item = EvidenceItem(
                evidence_type="signal",
                content=signal.raw_content[:5000],
                source_type=signal.type.value,
                source_reference=signal.source_url or str(signal.id),
                content_hash=signal.content_hash,
            )
            package.items.append(item)
        
        # Compute package hash
        package.finalize()
        
        logger.info(
            "evidence_package_created",
            case_id=str(case.id),
            items=len(package.items),
        )
        
        return package
    
    def export_json(self, package: Evidence) -> ExportResult:
        """Export evidence package as JSON."""
        content = json.dumps(
            package.model_dump(),
            indent=2,
            default=str,
        )
        
        file_path = self.output_dir / f"evidence_{package.id}.json"
        file_path.write_text(content, encoding="utf-8")
        
        return ExportResult(
            format="json",
            file_path=str(file_path),
            content=content,
            size_bytes=len(content.encode()),
            item_count=len(package.items),
            hash=package.integrity_hash or "",
            timestamp=datetime.utcnow(),
        )
    
    def export_html(self, package: Evidence) -> ExportResult:
        """Export evidence package as HTML report."""
        html = self._generate_html_report(package)
        
        file_path = self.output_dir / f"evidence_{package.id}.html"
        file_path.write_text(html, encoding="utf-8")
        
        return ExportResult(
            format="html",
            file_path=str(file_path),
            content=html,
            size_bytes=len(html.encode()),
            item_count=len(package.items),
            hash=package.integrity_hash or "",
            timestamp=datetime.utcnow(),
        )
    
    def _generate_html_report(self, package: Evidence) -> str:
        """Generate HTML evidence report."""
        items_html = ""
        for i, item in enumerate(package.items, 1):
            items_html += f"""
            <div class="evidence-item">
                <h3>Item {i}: {item.evidence_type.upper()}</h3>
                <table>
                    <tr><td><strong>Source:</strong></td><td>{item.source_type}</td></tr>
                    <tr><td><strong>Reference:</strong></td><td>{item.source_reference or 'N/A'}</td></tr>
                    <tr><td><strong>Hash:</strong></td><td><code>{item.content_hash or 'N/A'}</code></td></tr>
                    <tr><td><strong>Captured:</strong></td><td>{item.captured_at}</td></tr>
                </table>
                <div class="content">
                    <pre>{self._escape_html(item.content[:1000])}</pre>
                </div>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evidence Package: {package.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a2e; border-bottom: 3px solid #4a90d9; padding-bottom: 10px; }}
        h2 {{ color: #4a90d9; margin-top: 30px; }}
        .meta {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .meta table {{ width: 100%; border-collapse: collapse; }}
        .meta td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .evidence-item {{ border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 5px; }}
        .evidence-item h3 {{ margin-top: 0; color: #16213e; }}
        .content {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        pre {{ margin: 0; white-space: pre-wrap; word-wrap: break-word; font-size: 12px; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; }}
        .integrity {{ background: #d4edda; padding: 15px; border-radius: 5px; margin-top: 30px; }}
        footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 Evidence Package</h1>
        
        <div class="meta">
            <table>
                <tr><td><strong>Title:</strong></td><td>{package.title}</td></tr>
                <tr><td><strong>Case ID:</strong></td><td><code>{package.case_id}</code></td></tr>
                <tr><td><strong>Package ID:</strong></td><td><code>{package.id}</code></td></tr>
                <tr><td><strong>Created:</strong></td><td>{package.created_at}</td></tr>
                <tr><td><strong>Created By:</strong></td><td>{package.created_by}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{package.status}</td></tr>
            </table>
        </div>
        
        <p>{package.description or 'No description provided.'}</p>
        
        <h2>Evidence Items ({len(package.items)})</h2>
        {items_html}
        
        <div class="integrity">
            <strong>🔒 Integrity Hash:</strong><br>
            <code>{package.integrity_hash or 'Not finalized'}</code>
        </div>
        
        <footer>
            Generated by N-CIIA Evidence Packager<br>
            Report generated: {datetime.utcnow().isoformat()}
        </footer>
    </div>
</body>
</html>"""
        
        return html
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
    
    def generate_timeline_html(
        self,
        events: list[dict[str, Any]],
        title: str = "Investigation Timeline",
    ) -> str:
        """Generate HTML timeline visualization."""
        events_html = ""
        for event in events:
            events_html += f"""
            <div class="timeline-item">
                <div class="timeline-date">{event.get('timestamp', 'Unknown')}</div>
                <div class="timeline-content">
                    <h4>{event.get('title', 'Event')}</h4>
                    <p>{event.get('description', '')}</p>
                    <small>Source: {event.get('source', 'N/A')}</small>
                </div>
            </div>
            """
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: sans-serif; margin: 40px; background: #1a1a2e; color: #fff; }}
        h1 {{ text-align: center; }}
        .timeline {{ position: relative; max-width: 800px; margin: 0 auto; }}
        .timeline::before {{ content: ''; position: absolute; left: 50%; width: 2px; background: #4a90d9; height: 100%; }}
        .timeline-item {{ padding: 20px; position: relative; width: 45%; }}
        .timeline-item:nth-child(odd) {{ left: 0; }}
        .timeline-item:nth-child(even) {{ left: 55%; }}
        .timeline-date {{ color: #4a90d9; font-weight: bold; }}
        .timeline-content {{ background: #16213e; padding: 15px; border-radius: 8px; }}
        .timeline-content h4 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <h1>📅 {title}</h1>
    <div class="timeline">{events_html}</div>
</body>
</html>"""


# Global packager
_packager: Optional[EvidencePackager] = None


def get_packager() -> EvidencePackager:
    """Get or create evidence packager."""
    global _packager
    if _packager is None:
        _packager = EvidencePackager()
    return _packager
