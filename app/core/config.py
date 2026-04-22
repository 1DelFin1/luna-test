from pydantic import BaseModel, computed_field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresConfig(BaseModel):
    HOST: str
    PORT: int
    DATABASE: str
    USERNAME: str
    PASSWORD: str

    @computed_field
    @property
    def URL(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.USERNAME,
            password=self.PASSWORD,
            host=self.HOST,
            port=self.PORT,
            path=self.DATABASE,
        )


class RabbitMQConfig(BaseModel):
    HOST: str
    PORT: int = 5672
    USERNAME: str
    PASSWORD: str
    VHOST: str = "/"

    @computed_field
    @property
    def URL(self) -> str:
        return f"amqp://{self.USERNAME}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.VHOST}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    postgres_db: PostgresConfig
    rabbitmq: RabbitMQConfig
    api_key: str


settings = Settings()
