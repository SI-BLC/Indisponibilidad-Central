from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "indisponibilidad"

    # Active Directory
    LDAP_HOST: str = "blcglobal.net"
    LDAP_PORT: int = 389
    LDAP_DOMAIN: str = "blcglobal.net"
    LDAP_BASE_DN: str = "DC=blcglobal,DC=net"
    LDAP_BIND_USER: str = "ldap_si"
    LDAP_BIND_PASSWORD: str = ""
    LDAP_GROUP_PREFIX: str = "Security - BLC PG"

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    model_config = {"env_file": ".env"}


settings = Settings()
