from pydantic import BaseModel


class UserLogin(BaseModel):
    username: str
    password: str | None = None  # 可选，若配置了统一密码则可不传


class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class TokenPayload(BaseModel):
    sub: str  # user_id
    exp: int
    type: str = "access"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
