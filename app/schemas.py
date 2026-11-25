from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class TransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_client: ClientRef
    to_client: ClientRef
    amount: str
    currency: str
    effective_date: date
    external_id: ExternalId
    memo: Memo = None

    @model_validator(mode="after")
    def different_clients(self):
        if self.from_client == self.to_client:
            raise ValueError("from_client and to_client must differ")
        return self


class ReversalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class ImportIn(BaseModel):
    # Rows stay untyped here so one malformed row is reported on its own instead of failing the whole file.
    rows: list[Any] = Field(min_length=1, max_length=1000)
