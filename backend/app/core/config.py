from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883

    class Config:
        env_file = ".env"


settings = Settings()
