from typing import Any, Literal, Optional

from odoo.addons.core_fastapi.schemas import BaseModel
from pydantic import Field


class TicketIdentifier(BaseModel):
    id: int
    uuid: str | bool
    name: str | bool


class SerializedRecord(BaseModel):
    id: int
    model: str
    display_name: Any = False
    data: dict[str, Any] = Field(default_factory=dict)
    display_values: dict[str, Any] = Field(default_factory=dict)


class RelatedCollection(BaseModel):
    model: str
    count: int = 0
    returned_count: int = 0
    truncated: bool = False
    field_metadata: dict[str, Any] = Field(default_factory=dict)
    records: list[SerializedRecord] = Field(default_factory=list)


class TicketChatter(BaseModel):
    messages: Optional[RelatedCollection] = None
    activities: Optional[RelatedCollection] = None


class TicketEleAutFullDataResponse(BaseModel):
    model: str
    business_area: Literal['ELE', 'AUT']
    generated_at: str
    active: bool
    created_at: str | bool = False
    updated_at: str | bool = False
    start_date: str | bool = False
    end_date: str | bool = False
    replied_date: str | bool = False
    identifier: TicketIdentifier
    ticket: SerializedRecord
    field_metadata: dict[str, Any] = Field(default_factory=dict)
    related_records: dict[str, RelatedCollection] = Field(default_factory=dict)
    chatter: TicketChatter
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class TicketEleAutFullDataListResponse(BaseModel):
    count: int
    offset: int
    limit: int
    returned_count: int
    has_more: bool
    next_cursor: str | None = None
    snapshot_at: str
    server_time: str
    updated_since: str | None = None
    updated_until: str
    items: list[TicketEleAutFullDataResponse] = Field(default_factory=list)
