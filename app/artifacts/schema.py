
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ParameterSpec(BaseModel):
    type: Literal["string", "integer", "number", "boolean"]
    required: bool = True
    description: str


class LocatorSpec(BaseModel):
    strategy: Literal[
        "attribute",
        "role",
        "text",
        "css",
    ]

    tag: str | None = None
    attribute: str | None = None
    value: str | None = None

    role: str | None = None
    name: str | None = None

    selector: str | None = None

    @model_validator(mode="after")
    def validate_locator(self):
        if self.strategy == "attribute":
            if not all([
                self.tag,
                self.attribute,
                self.value,
            ]):
                raise ValueError(
                    "Attribute locator requires "
                    "tag, attribute and value"
                )

        elif self.strategy == "role":
            if not self.role or not self.name:
                raise ValueError(
                    "Role locator requires role and name"
                )

        elif self.strategy == "text":
            if not self.value:
                raise ValueError(
                    "Text locator requires value"
                )

        elif self.strategy == "css":
            if not self.selector:
                raise ValueError(
                    "CSS locator requires selector"
                )

        return self


class ExtractionSpec(BaseModel):
    source: Literal["visible_text"]
    pattern: str
    group: int = Field(default=1, ge=0)


class CheckpointSpec(BaseModel):
    type: Literal[
        "url_path",
        "text_visible",
        "element_visible",
        "input_value",
    ]

    expected: str | None = None
    target: LocatorSpec | None = None

    @model_validator(mode="after")
    def validate_checkpoint(self):
        if self.type in (
            "url_path",
            "text_visible",
            "input_value",
        ):
            if self.expected is None:
                raise ValueError(
                    f"{self.type} requires expected"
                )

        if self.type in (
            "element_visible",
            "input_value",
        ):
            if self.target is None:
                raise ValueError(
                    f"{self.type} requires target"
                )

        return self


class ActionStep(BaseModel):
    step_id: str

    action: Literal[
        "fill",
        "click",
        "extract",
    ]

    target: LocatorSpec | None = None

    value: str | None = None

    extraction: ExtractionSpec | None = None

    checkpoint: CheckpointSpec | None = None

    @model_validator(mode="after")
    def validate_step(self):
        if self.action in ("fill", "click"):
            if self.target is None:
                raise ValueError(
                    "Interactive steps require a target"
                )

        if self.action == "fill":
            if self.value is None:
                raise ValueError(
                    "Fill steps require a value"
                )

        if self.action == "extract":
            if self.extraction is None:
                raise ValueError(
                    "Extract steps require an extraction rule"
                )

        return self


class OutputSpec(BaseModel):
    type: Literal[
        "string",
        "integer",
        "number",
        "boolean",
    ]

    description: str

    source_step: str | None = None


class CapabilityArtifact(BaseModel):
    schema_version: str = "1.0"

    capability_id: str
    capability_version: str

    description: str

    target_app: str

    inputs: dict[str, ParameterSpec]

    outputs: dict[str, OutputSpec]

    steps: list[ActionStep]

    success_condition: dict[str, Any]

    expected_outcomes: dict[str, Any] = Field(
        default_factory=dict
    )
