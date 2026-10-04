from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./escape.db"
    secret_key: str = "development-only-change-me"
    admin_bootstrap_password: str = "change-me"
    game_duration_minutes: int = 50
    hint_penalty_points: int = 25
    hint_penalty_seconds: int = 120
    terminal_worker_socket: str = ""
    terminal_worker_url: str = "http://127.0.0.1:8080"
    max_teams: int = 30
    team_size: int = 3
    enable_bonus: bool = False
    leaderboard_enabled: bool = True

settings = Settings()
