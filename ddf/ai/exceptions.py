
class AIError(Exception):
    pass


class ModelRoutingError(AIError):
    pass


class NoSuitableModelError(ModelRoutingError):
    pass


class GuardrailError(AIError):
    pass
