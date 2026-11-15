import logging
from typing import Any, Dict, List, Optional

from ...agents.base_agent import BaseAgent
from ...agents.interfaces import Step
from ...utils.llm_utils import sanitize_prompt

logger = logging.getLogger("backend.agents.project_management")


class ProjectManagementAgent(BaseAgent):
    """Agent that turns business goals into prioritized execution plans."""

    def __init__(
        self,
        name: str = "project_management",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, config=config)

    async def _plan(
        self,
        goal: str = "",
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Step]:
        safe_goal = sanitize_prompt(goal or "Create a project plan.")
        return [
            {"type": "retrieve_knowledge", "payload": {"goal": safe_goal}},
            {
                "type": "plan",
                "payload": {"goal": safe_goal, "constraints": constraints or {}},
            },
            {"type": "status", "payload": {"goal": safe_goal}},
        ]

    async def _execute_step(self, step: Step, **kwargs: Any) -> Any:
        step_type = step.get("type")
        payload = step.get("payload", {}) or {}

        if step_type == "retrieve_knowledge":
            goal = payload.get("goal", "")
            knowledge_hits = await self.query_knowledge(query=goal, top_k=3)
            await self.remember("retrieved_knowledge", {"hits": knowledge_hits})
            return {"knowledge_hits": knowledge_hits}

        if step_type == "plan":
            knowledge_mem = await self.recall("retrieved_knowledge", limit=1)
            knowledge_context = ""
            if knowledge_mem and isinstance(knowledge_mem, list) and knowledge_mem[0].get("value"):
                hits = knowledge_mem[0]["value"].get("hits", [])
                if hits:
                    lines = [f"- [{h.get('title', 'SOP/Roadmap')}]: {h.get('content', '')}" for h in hits]
                    knowledge_context = f"\nRelevant Project SOP & Historical Knowledge:\n" + "\n".join(lines) + "\n"

            prompt = (
                f"Goal: {payload.get('goal', '')}\n"
                f"Constraints: {payload.get('constraints', {})}\n"
                f"{knowledge_context}\n"
                "Create a prioritized task plan with owners, dependencies, and milestones."
            )
            plan_text = await self.llm_generate(
                task="chat",
                prompt=prompt,
                model_hint=self.config.get("model"),
            )
            await self.remember("project_plan", {"text": plan_text})
            return {"plan": plan_text}

        if step_type == "status":
            plan_memory = await self.recall("project_plan", limit=1)
            plan_text = (
                plan_memory[0].get("value", {}).get("text", "")
                if plan_memory and isinstance(plan_memory[0], dict)
                else ""
            )
            prompt = (
                "Summarize the current project status, highlight blockers, and recommend "
                "the next most important actions based on this plan:\n\n"
                f"{plan_text}"
            )
            status_text = await self.llm_generate(
                task="content",
                prompt=prompt,
                model_hint=self.config.get("model"),
            )
            return {"status": status_text}

        tool_result = await self.call_tool(step_type, **payload)
        return {"tool_result": tool_result}
