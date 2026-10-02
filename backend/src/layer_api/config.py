from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://layer:layer@localhost:5433/layer"
    oauth_state_secret: str
    clerk_secret_key: str = ""
    clerk_jwt_key: str = ""
    frontend_url: str = "http://localhost:3000"
    rag_engine_url: str = "http://localhost:8000/mcp"
    rag_engine_api_key: str = ""
    composio_api_key: str = ""
    openai_api_key: str = ""
    llm_model_small: str = "gpt-4o-mini"
    llm_model_strong: str = "gpt-4o"
    composio_demo_user_id: str = "layer-demo"
    demo_token_secret: str = ""
    demo_questions_per_guest: int = 7
    demo_guest_ttl_hours: int = 24
    demo_collection_id: str = "layer-demo-phoenix"
    demo_drive_account_id: str = ""
    demo_gmail_account_id: str = ""
    demo_jira_account_id: str = ""
    demo_notion_account_id: str = ""
    demo_drive_folder_ids: str = ""
    demo_drive_file_ids: str = ""
    demo_notion_page_ids: str = ""
    demo_notion_database_ids: str = ""
    demo_gmail_label: str = "phoenix"
    demo_jira_project_key: str = "PHX"
    demo_sender_account_id: str = ""
    demo_recipient_email: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url
