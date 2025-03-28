from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString,
                                  single_argument_result)
from .cloud_sync_providers import CloudCredentialProvider

__all__ = ["CloudCredentialEntry",
           "CloudCredentialCreateArgs", "CloudCredentialCreateResult",
           "CloudCredentialUpdateArgs", "CloudCredentialUpdateResult",
           "CloudCredentialDeleteArgs", "CloudCredentialDeleteResult",
           "CloudCredentialVerifyArgs", "CloudCredentialVerifyResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: CloudCredentialProvider


class CloudCredentialCreate(CloudCredentialEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CloudCredentialCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate


class CloudCredentialCreateResult(BaseModel):
    result: CloudCredentialEntry


class CloudCredentialUpdateArgs(BaseModel):
    id: int
    cloud_sync_credentials_update: CloudCredentialUpdate


class CloudCredentialUpdateResult(BaseModel):
    result: CloudCredentialEntry


class CloudCredentialDeleteArgs(BaseModel):
    id: int


class CloudCredentialDeleteResult(BaseModel):
    result: bool


class CloudCredentialVerifyArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialProvider


@single_argument_result
class CloudCredentialVerifyResult(BaseModel):
    valid: bool
    error: LongString | None = None
    excerpt: LongString | None = None
