from typing import Union, Optional, Annotated, Literal
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    EmailStr,
    StringConstraints,
    field_validator,
)
from .wage import Wage


class PaymentMetadata(BaseModel):
    mobile: Annotated[str, StringConstraints(pattern=r"^09\d{9}$")] | None = None
    email: EmailStr | None = None
    order_id: str | None = None


class PaymentRequest(BaseModel):
    amount: Annotated[int, Field(ge=1000)]
    currency: Literal["IRR", "IRT"] = "IRR"
    description: str
    callback_url: HttpUrl  # HttpUrl already parses from str
    metadata: Union[PaymentMetadata, dict[str, Union[str, int]], None] = None
    referrer_id: Optional[str] = None
    wages: Optional[list[Wage]] = None  # Optional (no default_factory to avoid len([]) validation)

    @field_validator("wages")
    def check_wages_length(cls, v: Optional[list[Wage]]):
        if v is None:
            return v
        if not (1 <= len(v) <= 5):
            raise ValueError("wages must contain between 1 and 5 items")
        return v
