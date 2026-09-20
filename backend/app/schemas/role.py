from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name_ru: str
    name_uz: str | None = None
    name_en: str | None = None
    category: str
    permission_level: int
