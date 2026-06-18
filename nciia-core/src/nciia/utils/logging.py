"""
Structured Logging for N-CIIA

Production-grade logging with structured output, audit trails,
and configurable handlers.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from structlog.processors import CallsiteParameter


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    file_path: Optional[str] = None,
    include_timestamp: bool = True,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ('json' or 'console')
        file_path: Optional file path for log output
        include_timestamp: Whether to include timestamps
    """
    
    # Shared processors for all outputs
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if include_timestamp:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))
    
    # Add callsite info in debug mode
    if level == "DEBUG":
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                [
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.LINENO,
                    CallsiteParameter.FUNC_NAME,
                ]
            )
        )
    
    # Format-specific processors
    if format == "json":
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Add file handler if specified
    if file_path:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.getLogger().addHandler(file_handler)


class AuditLogger:
    """
    Specialized logger for audit trail events.
    
    Maintains immutable, timestamped records of all analyst
    and system actions for compliance and traceability.
    """
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._logger = structlog.get_logger("audit")
    
    def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        analyst_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        Log an auditable action.
        
        Args:
            action: Action performed (create, read, update, delete, search, export)
            entity_type: Type of entity affected (signal, persona, case, evidence)
            entity_id: ID of the affected entity
            analyst_id: ID of the analyst performing the action
            details: Additional action details
            success: Whether the action succeeded
        """
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "analyst_id": analyst_id or "system",
            "success": success,
            "details": details or {},
        }
        
        # Log to structured logger
        self._logger.info(
            "audit_event",
            **record,
        )
        
        # Also append to dedicated audit file (immutable append)
        self._append_to_file(record)
    
    def _append_to_file(self, record: dict[str, Any]) -> None:
        """Append record to audit file."""
        import json
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    
    def log_investigation_start(
        self,
        case_id: str,
        analyst_id: str,
        seed_type: str,
        seed_value: str,
    ) -> None:
        """Log the start of an investigation."""
        self.log_action(
            action="investigation_start",
            entity_type="case",
            entity_id=case_id,
            analyst_id=analyst_id,
            details={
                "seed_type": seed_type,
                "seed_value": seed_value,
            },
        )
    
    def log_investigation_complete(
        self,
        case_id: str,
        analyst_id: str,
        findings_count: int,
        duration_seconds: float,
    ) -> None:
        """Log the completion of an investigation."""
        self.log_action(
            action="investigation_complete",
            entity_type="case",
            entity_id=case_id,
            analyst_id=analyst_id,
            details={
                "findings_count": findings_count,
                "duration_seconds": duration_seconds,
            },
        )
    
    def log_evidence_export(
        self,
        evidence_id: str,
        analyst_id: str,
        export_format: str,
        file_path: str,
    ) -> None:
        """Log evidence export action."""
        self.log_action(
            action="evidence_export",
            entity_type="evidence",
            entity_id=evidence_id,
            analyst_id=analyst_id,
            details={
                "format": export_format,
                "file_path": file_path,
            },
        )
    
    def log_watcher_action(
        self,
        action: str,
        persona_id: str,
        analyst_id: Optional[str] = None,
    ) -> None:
        """Log watcher start/stop/pause actions."""
        self.log_action(
            action=f"watcher_{action}",
            entity_type="persona",
            entity_id=persona_id,
            analyst_id=analyst_id,
        )
    
    def log_llm_query(
        self,
        query_type: str,
        context_size: int,
        response_tokens: int,
        analyst_id: Optional[str] = None,
    ) -> None:
        """Log LLM usage for monitoring and cost tracking."""
        self.log_action(
            action="llm_query",
            entity_type="system",
            entity_id="llm_assistant",
            analyst_id=analyst_id,
            details={
                "query_type": query_type,
                "context_size": context_size,
                "response_tokens": response_tokens,
            },
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_file: str = "logs/audit.log") -> AuditLogger:
    """Get or create audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_file)
    return _audit_logger


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)
