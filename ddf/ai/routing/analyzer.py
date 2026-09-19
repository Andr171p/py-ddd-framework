from typing import Any

from collections.abc import Mapping, Sequence

from ddf.ai.models import Modality, ModelCapability

from .routing_request import ModelRoutingRequest


def analyze_response_request(
    params: Mapping[str, Any],
    *,
    estimated_input_tokens: int | None = None,
) -> ModelRoutingRequest:
    """"""

    modalities: set[Modality] = set()
    capabilities: set[ModelCapability] = set()
    input_text: list[str] = []

    instructions = params.get("instructions")

    if isinstance(instructions, str):
        input_text.append(instructions)
        modalities.add(Modality.TEXT)

    _analyze_input(
        params.get("input"),
        modalities=modalities,
        capabilities=capabilities,
        texts=input_text,
    )

    if params.get("tools"):
        capabilities.add(ModelCapability.TOOLS)

    if params.get("reasoning") is not None:
        capabilities.add(ModelCapability.REASONING)

    if _uses_structured_output(params.get("text")):
        capabilities.add(ModelCapability.STRUCTURED_OUTPUT)

    if not modalities:
        modalities.add(Modality.TEXT)

    text = "\n\n".join(t for t in input_text if t)

    return ModelRoutingRequest(
        input_modalities=frozenset(modalities),
        output_modalities=frozenset({Modality.TEXT}),
        required_capabilities=frozenset(capabilities),
        estimated_input_tokens=estimated_input_tokens,
        max_output_tokens=params.get("max_output_tokens"),
        input_text=text or None,
    )


def _analyze_input(  # noqa: C901
    value: Any,
    *,
    modalities: set[Modality],
    capabilities: set[ModelCapability],
    texts: list[str],
) -> None:
    """"""

    if value is None:
        return

    if isinstance(value, str):
        modalities.add(Modality.TEXT)
        texts.append(value)
        return

    if isinstance(value, Mapping):
        type_ = value.get("type")

        match type_:
            case "input_text":
                modalities.add(Modality.TEXT)

                if isinstance((text := value.get("text")), str):
                    texts.append(text)

                return

            case "input_image":
                modalities.add(Modality.IMAGE)
                return

            case "input_audio":
                modalities.add(Modality.AUDIO)
                return

            case "input_file":
                capabilities.add(ModelCapability.FILE_INPUT)
                return

        if (content := value.get("content")) is not None:
            _analyze_input(content, modalities=modalities, capabilities=capabilities, texts=texts)

        return

    if isinstance(value, Sequence):
        for item in value:
            _analyze_input(item, modalities=modalities, capabilities=capabilities, texts=texts)


def _uses_structured_output(text: Any) -> bool:
    """"""

    if not isinstance(text, Mapping):
        return False

    format_ = text.get("format")

    if not isinstance(format_, Mapping):
        return False

    return format_.get("type") in {"json_schema", "json_object"}
