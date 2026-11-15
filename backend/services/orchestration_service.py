from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import database
from ..models.agent_models import AGENT_TYPE_VALUES, Agent
from ..models.conversation_models import Conversation, Message
from ..models.task_models import Task
from ..models.user_models import User
from . import memory_service
from .agent_service import AgentServiceError, get_agent_service


class OrchestrationServiceError(Exception):
    """Raised when orchestration-level validation or coordination fails."""


class OrchestrationService:
    """Coordinates DB-backed chat, task, analytics, and agent runtime workflows."""

    def __init__(self) -> None:
        self.agent_service = get_agent_service()

    async def _run_db(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _session(self) -> Session:
        return database.SessionLocal()

    def _default_agent_name(self, agent_type: str) -> str:
        return agent_type.replace("_", " ").title()

    def _serialize_agent(self, agent: Agent) -> dict[str, Any]:
        return {
            "type": agent.type,
            "name": agent.name,
            "status": agent.status,
            "last_run_at": agent.last_run_at,
        }

    def _serialize_conversation(self, conversation: Conversation) -> dict[str, Any]:
        return {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "agent_type": conversation.agent_type,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }

    def _serialize_message(self, message: Message) -> dict[str, Any]:
        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "content": message.content,
            "tokens_used": message.tokens_used,
            "model": message.model,
            "created_at": message.created_at,
        }

    def _serialize_task(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "assigned_to": task.assigned_to,
            "created_by": task.created_by,
            "due_date": task.due_date,
            "agent_type": task.agent_type,
            "workflow_instance_id": task.workflow_instance_id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def _sync_ensure_agent_record(self, agent_type: str, user_id: Optional[int]) -> Agent:
        db = self._session()
        try:
            agent = db.query(Agent).filter(Agent.type == agent_type).first()
            if agent is None:
                agent = Agent(
                    type=agent_type,
                    name=self._default_agent_name(agent_type),
                    status="idle",
                    config={"agent_type": agent_type},
                    created_by=user_id,
                )
                db.add(agent)
                db.commit()
                db.refresh(agent)
            return agent
        finally:
            db.close()

    async def ensure_default_agents(self, user_id: Optional[int] = None) -> None:
        for agent_type in AGENT_TYPE_VALUES:
            await self._run_db(self._sync_ensure_agent_record, agent_type, user_id)

    def _sync_list_agent_statuses(self) -> list[dict[str, Any]]:
        db = self._session()
        try:
            agents = db.query(Agent).order_by(Agent.type.asc()).all()
            return [self._serialize_agent(agent) for agent in agents]
        finally:
            db.close()

    async def list_agent_statuses(
        self, user_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        await self.ensure_default_agents(user_id)
        return await self._run_db(self._sync_list_agent_statuses)

    def _sync_get_agent_status(self, agent_type: str) -> Optional[dict[str, Any]]:
        db = self._session()
        try:
            agent = db.query(Agent).filter(Agent.type == agent_type).first()
            return self._serialize_agent(agent) if agent else None
        finally:
            db.close()

    async def get_agent_status(
        self, agent_type: str, user_id: Optional[int] = None
    ) -> dict[str, Any]:
        await self.ensure_default_agents(user_id)
        status_data = await self._run_db(self._sync_get_agent_status, agent_type)
        if status_data is None:
            raise OrchestrationServiceError("Agent type not found")
        return status_data

    def _build_agent_payload(
        self,
        agent_type: str,
        input_text: str,
        context: Optional[dict[str, Any]] = None,
        conversation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        context = context or {}
        payload: dict[str, Any] = {"context": context}
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id

        if agent_type == "customer_service":
            payload["customer_message"] = input_text
            payload["customer_id"] = context.get("customer_id")
            return payload
        if agent_type == "sales_research":
            payload["query"] = input_text
            payload["limit"] = context.get("limit", 10)
            payload["outreach_tone"] = context.get("outreach_tone", "friendly")
            return payload
        if agent_type == "content_creation":
            payload["brief"] = input_text
            payload["tone"] = context.get("tone", "neutral")
            payload["target_audience"] = context.get("target_audience", "general")
            payload["length"] = context.get("length", "short")
            return payload
        if agent_type == "data_analysis":
            payload["question"] = input_text
            payload["dataset"] = context.get("dataset")
            return payload
        if agent_type == "project_management":
            payload["goal"] = input_text
            payload["constraints"] = context.get("constraints")
            return payload
        raise OrchestrationServiceError("Agent type not found")

    def _sync_update_agent_status(
        self,
        agent_type: str,
        status: str,
        last_run_at: Optional[datetime] = None,
        config: Optional[dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        db = self._session()
        try:
            agent = db.query(Agent).filter(Agent.type == agent_type).first()
            if agent is None:
                agent = Agent(
                    type=agent_type,
                    name=self._default_agent_name(agent_type),
                    status=status,
                    config=config or {"agent_type": agent_type},
                    created_by=user_id,
                )
                db.add(agent)
            else:
                agent.status = status
                if config is not None:
                    agent.config = config
            if last_run_at is not None:
                agent.last_run_at = last_run_at
            db.commit()
            db.refresh(agent)
            return self._serialize_agent(agent)
        finally:
            db.close()

    async def run_agent(
        self,
        agent_type: str,
        input_text: str,
        user_id: int,
        context: Optional[dict[str, Any]] = None,
        conversation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if agent_type not in AGENT_TYPE_VALUES:
            raise OrchestrationServiceError("Agent type not found")

        await self._run_db(
            self._sync_update_agent_status,
            agent_type,
            "running",
            None,
            {"agent_type": agent_type},
            user_id,
        )
        runtime = await self.agent_service.create_agent(
            agent_type=agent_type,
            name=self._default_agent_name(agent_type),
            config={"agent_type": agent_type},
        )
        payload = self._build_agent_payload(
            agent_type=agent_type,
            input_text=input_text,
            context=context,
            conversation_id=conversation_id,
        )
        started_at = datetime.now(timezone.utc)
        try:
            result = await self.agent_service.run_agent(runtime.id, payload=payload)
        except AgentServiceError as exc:
            await self._run_db(
                self._sync_update_agent_status,
                agent_type,
                "error",
                started_at,
                {"agent_type": agent_type},
                user_id,
            )
            raise OrchestrationServiceError(str(exc)) from exc
        except Exception as exc:
            await self._run_db(
                self._sync_update_agent_status,
                agent_type,
                "error",
                started_at,
                {"agent_type": agent_type},
                user_id,
            )
            raise OrchestrationServiceError(str(exc)) from exc

        final_status = "idle" if getattr(result, "success", False) else "error"
        await self._run_db(
            self._sync_update_agent_status,
            agent_type,
            final_status,
            datetime.now(timezone.utc),
            {"agent_type": agent_type},
            user_id,
        )
        return {
            "success": bool(getattr(result, "success", False)),
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
            "data": getattr(result, "data", {}) or {},
            "started_at": started_at,
        }

    async def list_agent_history(
        self, agent_type: str, skip: int = 0, limit: int = 20
    ) -> list[dict[str, Any]]:
        agents = self.agent_service.get_agents_by_type(agent_type)
        history: list[dict[str, Any]] = []
        for agent in agents:
            records = await memory_service.get_memory(
                agent_id=agent.id,
                key="audit",
                limit=skip + limit + 50,
            )
            for record in records:
                value = record.get("value", {}) or {}
                result = value.get("result", {}) or {}
                data = result.get("data", {}) or {}
                history.append(
                    {
                        "agent_id": value.get("agent_id", agent.id),
                        "agent_type": agent_type,
                        "timestamp": value.get("ts", record.get("ts")),
                        "payload": value.get("payload", {}),
                        "success": result.get("success", False),
                        "output": result.get("output"),
                        "error": result.get("error"),
                        "duration_ms": data.get("duration_ms", 0),
                    }
                )
        history.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        return history[skip : skip + limit]

    def _sync_get_conversation(
        self, user_id: int, conversation_id: int
    ) -> Optional[dict[str, Any]]:
        db = self._session()
        try:
            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
                .first()
            )
            if conversation is None:
                return None
            messages = (
                db.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc(), Message.id.asc())
                .all()
            )
            return {
                "conversation": self._serialize_conversation(conversation),
                "messages": [self._serialize_message(message) for message in messages],
            }
        finally:
            db.close()

    async def get_conversation(
        self, user_id: int, conversation_id: int
    ) -> dict[str, Any]:
        conversation = await self._run_db(
            self._sync_get_conversation, user_id, conversation_id
        )
        if conversation is None:
            raise OrchestrationServiceError("Conversation not found")
        return conversation

    def _sync_list_conversations(
        self, user_id: int, skip: int, limit: int
    ) -> list[dict[str, Any]]:
        db = self._session()
        try:
            conversations = (
                db.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            return [
                self._serialize_conversation(conversation)
                for conversation in conversations
            ]
        finally:
            db.close()

    async def list_conversations(
        self, user_id: int, skip: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        return await self._run_db(self._sync_list_conversations, user_id, skip, limit)

    def _sync_delete_conversation(self, user_id: int, conversation_id: int) -> bool:
        db = self._session()
        try:
            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
                .first()
            )
            if conversation is None:
                return False
            db.delete(conversation)
            db.commit()
            return True
        finally:
            db.close()

    async def delete_conversation(self, user_id: int, conversation_id: int) -> None:
        deleted = await self._run_db(
            self._sync_delete_conversation, user_id, conversation_id
        )
        if not deleted:
            raise OrchestrationServiceError("Conversation not found")

    def _sync_prepare_conversation(
        self,
        user_id: int,
        agent_type: str,
        message: str,
        conversation_id: Optional[int],
    ) -> dict[str, Any]:
        db = self._session()
        try:
            if conversation_id is not None:
                conversation = (
                    db.query(Conversation)
                    .filter(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id,
                    )
                    .first()
                )
                if conversation is None:
                    raise OrchestrationServiceError("Conversation not found")
                if conversation.agent_type != agent_type:
                    raise OrchestrationServiceError(
                        "Conversation agent type does not match request"
                    )
            else:
                title = message.strip()[:80] or f"{agent_type.replace('_', ' ').title()} chat"
                conversation = Conversation(
                    user_id=user_id,
                    agent_type=agent_type,
                    title=title,
                )
                db.add(conversation)
                db.flush()

            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=message,
            )
            db.add(user_message)
            db.commit()
            db.refresh(conversation)
            return self._serialize_conversation(conversation)
        finally:
            db.close()

    def _sync_store_assistant_reply(
        self, conversation_id: int, reply: str, model: Optional[str]
    ) -> None:
        db = self._session()
        try:
            db.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=reply,
                    model=model,
                )
            )
            conversation = (
                db.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .first()
            )
            if conversation is not None:
                conversation.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    async def send_chat_message(
        self,
        user_id: int,
        message: str,
        agent_type: str,
        conversation_id: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        conversation = await self._run_db(
            self._sync_prepare_conversation,
            user_id,
            agent_type,
            message,
            conversation_id,
        )
        agent_response = await self.run_agent(
            agent_type=agent_type,
            input_text=message,
            user_id=user_id,
            context=context,
            conversation_id=conversation["id"],
        )
        if not agent_response["success"]:
            raise OrchestrationServiceError(agent_response["error"] or "Agent run failed")

        reply = agent_response["output"] or ""
        await self._run_db(
            self._sync_store_assistant_reply,
            conversation["id"],
            reply,
            context.get("model_hint") if context else None,
        )
        return {"reply": reply, "conversation_id": conversation["id"]}

    def _sync_summary(self) -> dict[str, int]:
        db = self._session()
        try:
            total_conversations = db.query(Conversation).count()
            total_messages = db.query(Message).count()
            agents_active = db.query(Agent).filter(Agent.status != "stopped").count()
            return {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "agents_active": agents_active,
            }
        finally:
            db.close()

    async def get_summary(self) -> dict[str, int]:
        await self.ensure_default_agents()
        return await self._run_db(self._sync_summary)

    async def get_agent_metrics(self) -> list[dict[str, Any]]:
        await self.ensure_default_agents()
        status_rows = await self.list_agent_statuses()
        metrics: list[dict[str, Any]] = []
        for row in status_rows:
            history = await self.list_agent_history(row["type"], skip=0, limit=100)
            runs = len(history)
            successes = sum(1 for item in history if item.get("success"))
            duration_values = [
                item.get("duration_ms", 0)
                for item in history
                if item.get("duration_ms", 0)
            ]
            avg_latency_ms = (
                int(sum(duration_values) / len(duration_values))
                if duration_values
                else 0
            )
            success_rate = float(successes / runs) if runs else 0.0
            metrics.append(
                {
                    "agent_type": row["type"],
                    "runs": runs,
                    "success_rate": success_rate,
                    "avg_latency_ms": avg_latency_ms,
                }
            )
        return metrics

    def _sync_usage(self) -> list[dict[str, Any]]:
        db = self._session()
        try:
            conversation_rows = (
                db.query(
                    func.date(Conversation.created_at).label("date"),
                    func.count(Conversation.id).label("conversations"),
                )
                .group_by(func.date(Conversation.created_at))
                .all()
            )
            message_rows = (
                db.query(
                    func.date(Message.created_at).label("date"),
                    func.count(Message.id).label("messages"),
                )
                .group_by(func.date(Message.created_at))
                .all()
            )
            usage_map: dict[str, dict[str, Any]] = {}
            for row in conversation_rows:
                usage_map[str(row.date)] = {
                    "date": str(row.date),
                    "conversations": int(row.conversations or 0),
                    "messages": 0,
                }
            for row in message_rows:
                date_key = str(row.date)
                usage_map.setdefault(
                    date_key,
                    {"date": date_key, "conversations": 0, "messages": 0},
                )
                usage_map[date_key]["messages"] = int(row.messages or 0)
            return [usage_map[key] for key in sorted(usage_map.keys())]
        finally:
            db.close()

    async def get_usage(self) -> list[dict[str, Any]]:
        return await self._run_db(self._sync_usage)

    def _validate_assignee(self, db: Session, assigned_to: Optional[int]) -> None:
        if assigned_to is None:
            return
        user = db.query(User).filter(User.id == assigned_to).first()
        if user is None or not user.is_active:
            raise OrchestrationServiceError("Assignee must be an existing active user")

    def _validate_task_transition(self, current_status: str, new_status: str) -> None:
        allowed = {
            "pending": {"pending", "in_progress", "cancelled"},
            "in_progress": {"in_progress", "done", "cancelled"},
            "done": {"done"},
            "cancelled": {"cancelled"},
        }
        if new_status not in allowed.get(current_status, {current_status}):
            raise OrchestrationServiceError("Invalid task status transition")

    def _sync_list_tasks(
        self,
        current_user_id: int,
        is_admin: bool,
        skip: int,
        limit: int,
        status_filter: Optional[str],
        assigned_to: Optional[int],
    ) -> list[dict[str, Any]]:
        db = self._session()
        try:
            query = db.query(Task)
            if not is_admin:
                query = query.filter(
                    (Task.created_by == current_user_id)
                    | (Task.assigned_to == current_user_id)
                )
            if status_filter:
                query = query.filter(Task.status == status_filter)
            if assigned_to is not None:
                query = query.filter(Task.assigned_to == assigned_to)
            tasks = (
                query.order_by(Task.created_at.desc(), Task.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            return [self._serialize_task(task) for task in tasks]
        finally:
            db.close()

    async def list_tasks(
        self,
        current_user_id: int,
        is_admin: bool,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        assigned_to: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return await self._run_db(
            self._sync_list_tasks,
            current_user_id,
            is_admin,
            skip,
            limit,
            status_filter,
            assigned_to,
        )

    def _sync_get_task(
        self, task_id: int, current_user_id: int, is_admin: bool
    ) -> Optional[dict[str, Any]]:
        db = self._session()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return None
            if (
                not is_admin
                and task.created_by != current_user_id
                and task.assigned_to != current_user_id
            ):
                raise OrchestrationServiceError("Not authorized to access this task")
            return self._serialize_task(task)
        finally:
            db.close()

    async def get_task(
        self, task_id: int, current_user_id: int, is_admin: bool
    ) -> dict[str, Any]:
        task = await self._run_db(
            self._sync_get_task, task_id, current_user_id, is_admin
        )
        if task is None:
            raise OrchestrationServiceError("Task not found")
        return task

    def _sync_create_task(
        self,
        payload: dict[str, Any],
        current_user_id: int,
    ) -> dict[str, Any]:
        db = self._session()
        try:
            assigned_to = payload.get("assigned_to")
            self._validate_assignee(db, assigned_to)
            task = Task(
                title=payload["title"],
                description=payload.get("description"),
                status=payload.get("status") or "pending",
                priority=payload.get("priority") or "medium",
                assigned_to=assigned_to,
                created_by=current_user_id,
                due_date=payload.get("due_date"),
                agent_type=payload.get("agent_type"),
                workflow_instance_id=payload.get("workflow_instance_id"),
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return self._serialize_task(task)
        finally:
            db.close()

    async def create_task(
        self,
        payload: dict[str, Any],
        current_user_id: int,
    ) -> dict[str, Any]:
        return await self._run_db(self._sync_create_task, payload, current_user_id)

    def _sync_update_task(
        self,
        task_id: int,
        payload: dict[str, Any],
        current_user_id: int,
        is_admin: bool,
    ) -> Optional[dict[str, Any]]:
        db = self._session()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return None
            if (
                not is_admin
                and task.created_by != current_user_id
                and task.assigned_to != current_user_id
            ):
                raise OrchestrationServiceError("Not authorized to update this task")
            if "assigned_to" in payload:
                self._validate_assignee(db, payload.get("assigned_to"))
            if "status" in payload and payload["status"] is not None:
                self._validate_task_transition(task.status, payload["status"])
            for field_name, field_value in payload.items():
                setattr(task, field_name, field_value)
            db.add(task)
            db.commit()
            db.refresh(task)
            return self._serialize_task(task)
        finally:
            db.close()

    async def update_task(
        self,
        task_id: int,
        payload: dict[str, Any],
        current_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        task = await self._run_db(
            self._sync_update_task,
            task_id,
            payload,
            current_user_id,
            is_admin,
        )
        if task is None:
            raise OrchestrationServiceError("Task not found")
        return task

    def _sync_delete_task(
        self,
        task_id: int,
        current_user_id: int,
        is_admin: bool,
    ) -> bool:
        db = self._session()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return False
            if not is_admin and task.created_by != current_user_id:
                raise OrchestrationServiceError("Not authorized to delete this task")
            db.delete(task)
            db.commit()
            return True
        finally:
            db.close()

    async def delete_task(
        self,
        task_id: int,
        current_user_id: int,
        is_admin: bool,
    ) -> None:
        deleted = await self._run_db(
            self._sync_delete_task,
            task_id,
            current_user_id,
            is_admin,
        )
        if not deleted:
            raise OrchestrationServiceError("Task not found")


_default_orchestration_service: Optional[OrchestrationService] = None


def get_orchestration_service() -> OrchestrationService:
    global _default_orchestration_service
    if _default_orchestration_service is None:
        _default_orchestration_service = OrchestrationService()
    return _default_orchestration_service
