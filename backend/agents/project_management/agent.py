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
            {
                "type": "plan",
                "payload": {"goal": safe_goal, "constraints": constraints or {}},
            },
            {"type": "status", "payload": {"goal": safe_goal}},
        ]

    async def _execute_step(self, step: Step, **kwargs: Any) -> Any:
        step_type = step.get("type")
        payload = step.get("payload", {}) or {}

        if step_type == "plan":
            prompt = (
                f"Goal: {payload.get('goal', '')}\n"
                f"Constraints: {payload.get('constraints', {})}\n\n"
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
