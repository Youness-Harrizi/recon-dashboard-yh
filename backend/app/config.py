from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://recon:recon@postgres:5432/recon"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:3000"
    # Optional — enables the `github` module's code search. Unset = module skips.
    github_token: str = ""
    # Optional — enables the `shodan` module. Unset = module skips.
    shodan_api_key: str = ""
    user_agent: str = "recon-dashboard-yh/0.1 (+https://github.com/Youness-Harrizi/recon-dashboard-yh)"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
