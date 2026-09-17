from dataclasses import dataclass, field

from email_validator import EmailNotValidError, validate_email


@dataclass(frozen=True, slots=True)
class Email:
    value: str = field(compare=True, hash=True)

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Email cannot be empty")

        try:
            validation = validate_email(self.value, check_deliverability=False)
            normalized = validation.normalized
        except EmailNotValidError as e:
            raise ValueError("Invalid email address") from e

        object.__setattr__(self, "string", normalized)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Email({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Email):
            return self.value == other.value

        if isinstance(other, str):
            try:
                validation = validate_email(self.value, check_deliverability=False)
            except EmailNotValidError:
                return False
            else:
                return self.value == validation.normalized

        return NotImplemented

    @property
    def domain(self) -> str:
        return self.value.split("@")[-1]
