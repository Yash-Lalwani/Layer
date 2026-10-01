from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://layer:layer@localhost:5433/layer"
    jwt_secret: str
    frontend_url: str = "http://localhost:3000"
    rag_engine_url: str = "http://localhost:8000/mcp"
    rag_engine_api_key: str = ""
    composio_api_key: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url
