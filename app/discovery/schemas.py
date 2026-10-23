
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class AgentAction(BaseModel):
    action: Literal[
        "click", "fill", "extract", "finish", "blocked"
    ]

    control_id: int | None = Field(
        default=None,
        description="ID of an observed UI control",
    )

    value: str | None = None
    reasoning: str

    @model_validator(mode="after")
    def validate_action(self):
        if self.action in ("click", "fill"):
            if self.control_id is None:
                raise ValueError(
                    "click and fill require control_id"
                )

        if self.action == "fill" and self.value is None:
            raise ValueError("fill requires a value")

        if self.action in ("extract", "finish", "blocked"):
            if self.control_id is not None:
                raise ValueError(
                    "This action must not have a control_id"
                )

        return self
