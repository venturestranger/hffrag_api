class Config:
	EMBEDDING_MODEL = 'distiluse-base-multilingual-cased-v1'
	SECRET_KEY = 'admin123'
	AUTH_KEY = 'admin123'
	ISSUER = 'server'
	PORT = 4321
	SESSIONS_DB_PATH = './storage/sessions.sql'
	LLM_DRIVERS_DB_PATH = './storage/llm_drivers.sql'
	SESSION_LIFETIME = 3600


class Development(Config):
	pass


class Production(Config):
	pass


configs = {
	'dev': Development,
	'prod': Production,

	'default': Config
}
