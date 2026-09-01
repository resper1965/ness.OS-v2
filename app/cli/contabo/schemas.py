from typing import Optional
from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_expires_in: int
    token_type: str
    not_before_policy: int = Field(alias="not-before-policy")
    scope: str

class TagResponse(BaseModel):
    tagId: int
    name: str
    color: str

class InstanceResponse(BaseModel):
    instanceId: int
    name: str
    displayName: str
    status: str
    ipConfig: dict

class ObjectStorageResponse(BaseModel):
    objectStorageId: str
    totalPurchasedSpaceTB: float
    totalPurchasedSpaceMB: float
    status: str
    region: str
