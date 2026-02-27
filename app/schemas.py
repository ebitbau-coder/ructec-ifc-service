from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    tenant_id: str
    name: str
