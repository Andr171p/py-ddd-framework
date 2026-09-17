from typing import Protocol


class Serializer[T](Protocol):

    def dumps(self, value: T) -> bytes: ...

    def loads(self, value: bytes) -> T: ...
