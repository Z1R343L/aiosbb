__all__ = "Validations"

from dataclasses import dataclass


@dataclass
class Validations:
    def __post_init__(self) -> None:
        for name, _field in self.__dataclass_fields__.items():
            if method := getattr(self, f"_validate_{name}", None):
                setattr(self, name, method(getattr(self, name), field=_field))
