from pydantic import BaseModel


class PlatformAuthUser(BaseModel):
    id: int
    username: str
    nickname: str
    email: str
    avatar: str | None = None


class PlatformAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: PlatformAuthUser
    roles: list[str]
    permissions: list[str]
    permission_version: int


class PlatformMeResponse(BaseModel):
    user: PlatformAuthUser
    roles: list[str]
    permissions: list[str]
    permission_version: int
