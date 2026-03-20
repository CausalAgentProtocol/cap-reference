from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    version: str


class ServiceMetaResponse(BaseModel):
    name: str
    version: str
    docs: str
    openapi: str
