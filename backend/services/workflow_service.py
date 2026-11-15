from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from orchestration.graph_builder import GraphBuilder, GraphBuilderError
from orchestration.state_management import StateManager, get_state_manager
from orchestration.visualizer import Visualizer
from orchestration.workflow_executor import WorkflowExecutor

from ..core import database
from ..models.workflow_models import Workflow
from ..schemas import orchestration_schemas as _schemas

logger = logging.getLogger(__name__)


class WorkflowServiceError(Exception):
    pass


class WorkflowService:
    """
    High-level service for workflow CRUD, execution and monitoring with tenant isolation.
    Persists workflow definitions to the 'workflows' database table and partitions in-memory
    execution graphs by (user_id, workflow_name).
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        state_manager: Optional[StateManager] = None,
    ):
        self.persist_dir = (
            persist_dir
            or os.getenv("WORKFLOW_DIR")
            or os.path.join(os.getcwd(), "data", "workflows")
        )
        os.makedirs(self.persist_dir, exist_ok=True)
        # Keyed by (user_id, workflow_name)
        self._graphs: Dict[Tuple[int, str], GraphBuilder] = {}
        self._defs: Dict[Tuple[int, str], _schemas.WorkflowDefinition] = {}
        self.state_manager = state_manager or get_state_manager()
        self.executor = WorkflowExecutor(state_manager=self.state_manager)
        logger.debug("WorkflowService initialized persist_dir=%s", self.persist_dir)
        self._load_from_db()
        self._load_legacy_files()

    def _path_for(self, name: str, user_id: int = 1) -> str:
        tenant_dir = os.path.join(self.persist_dir, str(user_id))
        os.makedirs(tenant_dir, exist_ok=True)
        safe = name.replace("/", "_")
        return os.path.join(tenant_dir, f"{safe}.json")

    def _load_from_db(self) -> None:
        db = database.SessionLocal()
        try:
            records = db.query(Workflow).all()
            for r in records:
                try:
                    defn = _schemas.WorkflowDefinition(**r.definition)
                    key = (r.user_id, r.name)
                    self._defs[key] = defn
                    self._graphs[key] = self._build_graph_from_definition(defn)
                except Exception:
                    logger.exception("Failed to parse workflow definition id=%s", r.id)
        except Exception:
            logger.debug("Workflows table not yet initialized or query failed")
        finally:
            db.close()

    def _load_legacy_files(self) -> None:
        """Load legacy root-level workflow JSON files (assigned to default user_id=1)."""
        if not os.path.exists(self.persist_dir):
            return
        for fname in os.listdir(self.persist_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.persist_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                defn = _schemas.WorkflowDefinition(**payload)
                key = (1, defn.name)
                if key not in self._defs:
                    self._defs[key] = defn
                    self._graphs[key] = self._build_graph_from_definition(defn)
            except Exception:
                logger.debug("Failed to load legacy workflow file %s", path, exc_info=True)

    def _persist_to_db(self, defn: _schemas.WorkflowDefinition, user_id: int) -> None:
        db = database.SessionLocal()
        try:
            record = (
                db.query(Workflow)
                .filter(Workflow.name == defn.name, Workflow.user_id == user_id)
                .first()
            )
            data = defn.model_dump()
            if record is None:
                record = Workflow(
                    user_id=user_id,
                    name=defn.name,
                    description=defn.description,
                    definition=data,
                )
                db.add(record)
            else:
                record.description = defn.description
                record.definition = data
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("Failed to persist workflow %s to DB", defn.name)
            raise WorkflowServiceError(str(e)) from e
        finally:
            db.close()

    def _delete_from_db(self, name: str, user_id: int) -> None:
        db = database.SessionLocal()
        try:
            record = (
                db.query(Workflow)
                .filter(Workflow.name == name, Workflow.user_id == user_id)
                .first()
            )
            if record is not None:
                db.delete(record)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete workflow %s from DB", name)
            raise WorkflowServiceError(str(e)) from e
        finally:
            db.close()

    def _build_graph_from_definition(
        self, defn: _schemas.WorkflowDefinition
    ) -> GraphBuilder:
        g = GraphBuilder(name=defn.name)
        for ag_name, meta in (defn.agents or {}).items():
            g.register_agent(ag_name, metadata=meta)
        for node in defn.nodes:
            g.add_node(
                node.id,
                agent=node.agent,
                config=node.config or {},
                description=node.description,
            )
        for edge in defn.edges:
            g.add_edge(
                edge.src,
                edge.dst,
                condition=edge.condition,
                metadata=edge.metadata or {},
            )
        return g

    async def create_workflow(
        self, defn: _schemas.WorkflowDefinition, user_id: int = 1
    ) -> Dict[str, Any]:
        key = (user_id, defn.name)
        if key in self._defs:
            raise WorkflowServiceError(f"workflow exists: {defn.name}")
        try:
            graph = self._build_graph_from_definition(defn)
        except GraphBuilderError as e:
            raise WorkflowServiceError(str(e)) from e

        self._persist_to_db(defn, user_id)
        self._defs[key] = defn
        self._graphs[key] = graph
        return {"name": defn.name, "nodes": len(defn.nodes), "edges": len(defn.edges)}

    async def update_workflow(
        self, defn: _schemas.WorkflowDefinition, user_id: int = 1
    ) -> Dict[str, Any]:
        key = (user_id, defn.name)
        if key not in self._defs:
            raise WorkflowServiceError(f"workflow not found: {defn.name}")
        try:
            graph = self._build_graph_from_definition(defn)
        except GraphBuilderError as e:
            raise WorkflowServiceError(str(e)) from e

        self._persist_to_db(defn, user_id)
        self._defs[key] = defn
        self._graphs[key] = graph
        return {"name": defn.name, "updated": True}

    async def delete_workflow(self, name: str, user_id: int = 1) -> None:
        key = (user_id, name)
        if key not in self._defs:
            raise WorkflowServiceError(f"workflow not found: {name}")

        self._delete_from_db(name, user_id)
        self._defs.pop(key, None)
        self._graphs.pop(key, None)
        path = self._path_for(name, user_id=user_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    async def list_workflows(
        self, user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for (uid, name), defn in self._defs.items():
            if user_id is None or uid == user_id:
                results.append(
                    {"name": name, "nodes": len(defn.nodes), "edges": len(defn.edges)}
                )
        return results

    async def get_workflow(
        self, name: str, user_id: Optional[int] = None
    ) -> Optional[_schemas.WorkflowDefinition]:
        if user_id is not None:
            return self._defs.get((user_id, name))
        for (uid, n), defn in self._defs.items():
            if n == name:
                return defn
        return None

    def _get_graph(
        self, workflow_name: str, user_id: Optional[int] = None
    ) -> Optional[GraphBuilder]:
        if user_id is not None:
            return self._graphs.get((user_id, workflow_name))
        for (uid, n), g in self._graphs.items():
            if n == workflow_name:
                return g
        return None

    async def start(
        self,
        workflow_name: str,
        start_node: str,
        initial_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> str:
        graph = self._get_graph(workflow_name, user_id=user_id)
        if not graph:
            raise WorkflowServiceError(f"workflow not found: {workflow_name}")
        meta = dict(metadata or {})
        if user_id is not None:
            meta["user_id"] = user_id
        return await self.executor.start(
            graph=graph,
            start_node=start_node,
            initial_context=initial_context,
            metadata=meta,
        )

    async def run_and_wait(
        self,
        workflow_name: str,
        start_node: str,
        initial_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        graph = self._get_graph(workflow_name, user_id=user_id)
        if not graph:
            raise WorkflowServiceError(f"workflow not found: {workflow_name}")
        meta = dict(metadata or {})
        if user_id is not None:
            meta["user_id"] = user_id
        return await self.executor.run_and_wait(
            graph=graph,
            start_node=start_node,
            initial_context=initial_context,
            metadata=meta,
            timeout=timeout,
        )

    async def get_instance(
        self, instance_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        st = await self.state_manager.get_instance(instance_id)
        if not st:
            return None
        if user_id is not None:
            inst_user = (st.metadata or {}).get("user_id")
            if inst_user is not None and inst_user != user_id:
                return None
        return {
            "id": st.id,
            "workflow_name": st.workflow_name,
            "context": st.context,
            "metadata": st.metadata,
            "created_at": st.created_at,
            "updated_at": st.updated_at,
        }

    async def list_instances(
        self, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        all_instances = await self.state_manager.list_instances()
        if user_id is None:
            return all_instances
        filtered: Dict[str, Any] = {}
        for inst_id, data in all_instances.items():
            meta = (data or {}).get("metadata") or {}
            inst_user = meta.get("user_id")
            if inst_user is None or inst_user == user_id:
                filtered[inst_id] = data
        return filtered

    async def snapshot_instance(
        self, instance_id: str, out_path: Optional[str] = None
    ) -> str:
        return await self.state_manager.snapshot_instance(
            instance_id, out_path=out_path
        )

    async def export_visualization(
        self,
        workflow_name: str,
        out_dir: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, str]:
        graph = self._get_graph(workflow_name, user_id=user_id)
        if not graph:
            raise WorkflowServiceError(f"workflow not found: {workflow_name}")
        out_dir = out_dir or os.path.join(self.persist_dir, "visuals")
        os.makedirs(out_dir, exist_ok=True)
        viz = Visualizer(graph)
        mermaid_p = os.path.join(out_dir, f"{workflow_name}.mmd")
        dot_p = os.path.join(out_dir, f"{workflow_name}.dot")
        viz.save_mermaid(mermaid_p)
        viz.save_dot(dot_p)
        svg_bytes = viz.render_svg()
        svg_p = None
        if svg_bytes:
            svg_p = os.path.join(out_dir, f"{workflow_name}.svg")
            viz.save_svg(svg_p, svg_bytes) if hasattr(viz, "save_svg") else None
        return {"mermaid": mermaid_p, "dot": dot_p, "svg": svg_p or ""}


_default_workflow_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    global _default_workflow_service
    if _default_workflow_service is None:
        _default_workflow_service = WorkflowService()
    return _default_workflow_service
