from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ClientRef = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
ExternalId = Annotated[str, Field(min_length=1, max_length=128)]
Memo = Annotated[str | None, Field(default=None, max_length=500)]


class EntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_ref: ClientRef
    type: Literal["deposit", "withdrawal", "fee"]
    amount: str
    currency: str
    effective_date: date
    external_id: ExternalId
    memo: Memo = None
