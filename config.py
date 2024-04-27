class Config:
	SECRET_KEY = 'admin123'
	AUTH_KEY = 'admin123'
	ISSUER = 'server'
	PORT = 4321
	SESSIONS_DB_PATH = './storage/sessions.sql'
	SESSION_LIFETIME = 60


class Development(Config):
	pass


class Production(Config):
	pass


configs = {
	'dev': Development,
	'prod': Production,

	'default': Development
}
