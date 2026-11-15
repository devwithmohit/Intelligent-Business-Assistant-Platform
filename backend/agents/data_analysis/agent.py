import logging
from typing import Any, Dict, List, Optional

from ...agents.base_agent import BaseAgent
from ...agents.interfaces import Step
from ...utils.llm_utils import sanitize_prompt

logger = logging.getLogger("backend.agents.data_analysis")


class DataAnalysisAgent(BaseAgent):
    """Agent that analyzes structured business data and returns summarized findings."""

    def __init__(
        self,
        name: str = "data_analysis",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, config=config)

    async def _plan(
        self,
        dataset: Optional[List[Dict[str, Any]]] = None,
        question: str = "",
        **kwargs: Any,
    ) -> List[Step]:
        prompt = sanitize_prompt(question or "Analyze the provided business dataset.")
        return [
            {"type": "analyze", "payload": {"dataset": dataset or [], "question": prompt}},
            {"type": "summarize", "payload": {"question": prompt}},
        ]

    async def _execute_step(self, step: Step, **kwargs: Any) -> Any:
        step_type = step.get("type")
        payload = step.get("payload", {}) or {}

        if step_type == "analyze":
            dataset = payload.get("dataset", [])
            question = payload.get("question", "Analyze the dataset.")
            prompt = (
                f"Question: {question}\n\n"
                f"Dataset:\n{dataset}\n\n"
                "Return key findings, anomalies, and recommended business actions."
            )
            analysis = await self.llm_generate(
                task="chat",
                prompt=prompt,
                model_hint=self.config.get("model"),
            )
            await self.remember("analysis", {"text": analysis, "dataset_size": len(dataset)})
            return {"analysis": analysis}

        if step_type == "summarize":
            memory = await self.recall("analysis", limit=1)
            analysis_text = (
                memory[0].get("value", {}).get("text", "")
                if memory and isinstance(memory[0], dict)
                else ""
            )
            prompt = (
                "Turn the following business analysis into a short executive summary "
                "with bullet points and a KPI-focused close:\n\n"
                f"{analysis_text}"
            )
            summary = await self.llm_generate(
                task="content",
                prompt=prompt,
                model_hint=self.config.get("model"),
            )
            return {"summary": summary}

        tool_result = await self.call_tool(step_type, **payload)
        return {"tool_result": tool_result}
