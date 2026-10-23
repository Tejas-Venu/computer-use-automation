
import json
import os

from ollama import AsyncClient
from pydantic import ValidationError

from app.discovery.schemas import AgentAction



SYSTEM_PROMPT = """
You are a UI automation controller.

Choose exactly ONE next action based on the
current page and the user's goal.

Allowed actions:
- fill: Enter text into an observed input.
- click: Click an observed button or link.
- extract: Read requested data from the page.
- finish: Stop after extraction.
- blocked: Cannot safely proceed.

Rules:
1. For fill and click, use an observed control_id.
2. For fill, provide the value.
3. For extract, put the requested value in value.
4. For finish and blocked, control_id must be null.
5. Never invent controls.
6. Never perform financial transactions.
7. Keep reasoning under 15 words.
8. Return valid JSON only.

/no_think
"""



class DiscoveryAgent:
    def __init__(self):
        self.client = AsyncClient(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://host.docker.internal:11434"
            )
        )
        self.model = os.getenv(
            "OLLAMA_MODEL",
            "qwen3-vl:4b"
        )

    
    async def decide(
        self,
        goal: str,
        observation: dict,
        history: list[dict],
    ) -> AgentAction:
        
        compact_history = [
            {
                "action": item["action"]["action"],
                "control_id": item["action"].get("control_id"),
                "value": (
                    item["action"].get("value")
                    if item["action"]["action"] == "fill"
                    else None
                ),
            }
            for item in history[-5:]
        ]


        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps({
                    "goal": goal,
                    "observation": observation,
                    "previous_actions": compact_history,
                }),
            },
        ]

        last_error = None

        for attempt in range(2):
            try:
                response = await self.client.chat(
                    model=self.model,
                    messages=messages,
                    format=AgentAction.model_json_schema(),
                    options={
                        "temperature": 0,
                        "num_predict": 1024,
                    },
                    think=False,
                )

                content = response.message.content

                if not content or not content.strip():
                    raise ValueError(
                        "Ollama returned empty response content. "
                        f"done_reason={response.done_reason}"
                    )

                return AgentAction.model_validate_json(
                    content
                )

            except (ValueError, ValidationError) as exc:
                last_error = exc

                print(
                    f"LLM response validation failed "
                    f"(attempt {attempt + 1}/2): {exc}"
                )

        raise RuntimeError(
            "LLM failed to produce a valid action "
            "after 2 attempts"
        ) from last_error

