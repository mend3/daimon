"""Persist workflows and execution records as JSON files under ~/.hermes/ella_flow/.
Simple and inspectable; the canvas is the real source of truth in the user's head."""
from __future__ import annotations

import json
from pathlib import Path

from .model import Execution, Workflow

_ROOT = Path("~/.hermes/ella_flow").expanduser()


class FlowStore:
    def __init__(self, root: Path | None = None):
        self.root = root or _ROOT
        (self.root / "workflows").mkdir(parents=True, exist_ok=True)
        (self.root / "executions").mkdir(parents=True, exist_ok=True)

    def save_workflow(self, wf: Workflow) -> None:
        (self.root / "workflows" / f"{wf.id}.json").write_text(wf.model_dump_json(indent=2))

    def get_workflow(self, wf_id: str) -> Workflow | None:
        p = self.root / "workflows" / f"{wf_id}.json"
        return Workflow.model_validate_json(p.read_text()) if p.exists() else None

    def list_workflows(self) -> list[Workflow]:
        return [Workflow.model_validate_json(p.read_text())
                for p in sorted((self.root / "workflows").glob("*.json"))]

    def delete_workflow(self, wf_id: str) -> bool:
        p = self.root / "workflows" / f"{wf_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    def save_execution(self, ex: Execution) -> None:
        d = self.root / "executions" / ex.workflow_id
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ex.id}.json").write_text(ex.model_dump_json(indent=2))

    def list_executions(self, wf_id: str, limit: int = 50) -> list[Execution]:
        d = self.root / "executions" / wf_id
        if not d.exists():
            return []
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return [Execution.model_validate_json(p.read_text()) for p in files]
