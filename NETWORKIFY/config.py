import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL","sqlite:///powersys.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY",'jwt_secret_secret')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_EXPIRES", 3600))
    CELERY_BROKER_URL = os.getenv("REDIS_URL",'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", 'redis://localhost:6379/0')
    CORS_ORIGIN = os.getenv("CORS_ORIGINS",'*')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = 60

config_map =  {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}