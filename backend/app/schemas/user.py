from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Gender = Literal["male", "female", "other", "unknown"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    email: str
    phone: str | None = None
    role: str
    status: str
    department: str | None = None
    department_id: int | None = None
    birthday: date | None = None
    gender: Gender | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    nickname: str = Field(min_length=1, max_length=64)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    role: str = "viewer"
    status: str = "active"
    department_id: int | None = None
    birthday: date | None = None
    gender: Gender | None = None
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    role: str | None = None
    status: str | None = None
    department_id: int | None = None
    birthday: date | None = None
    gender: Gender | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class ResetPasswordResult(BaseModel):
    password: str
