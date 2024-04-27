from config import configs
from datetime import datetime
from datetime import timedelta
import sqlite3


config = configs['dev']
rag_drivers = {}


# initialize a session database
def init_sessions_db():
	conn = sqlite3.connect(config.SESSIONS_DB_PATH)
	cur = conn.cursor()
	cur.execute("""
		CREATE TABLE IF NOT EXISTS sessions(
			id INTEGER PRIMARY KEY,
			issued_when TEXT NOT NULL
		)
	""")
	conn.commit()
	conn.close()
	

# initialize session
def init_session(sess_id: int) -> bool:
	conn = sqlite3.connect(config.SESSIONS_DB_PATH)
	cur = conn.cursor()

	cur.execute("DELETE FROM sessions WHERE issued_when < ?", (str(datetime.now() - timedelta(seconds=config.SESSION_LIFETIME)),))
	conn.commit()

	cur.execute("SELECT * FROM sessions WHERE id = ?", (sess_id,))
	dat = cur.fetchall()

	# if not found, initialize a new session with sess_id
	if len(dat) == 0:
		# clean up a RAG driver previously associated with this session id
		rag_drivers.pop(sess_id) 
		# rag_drivers[sess_id] = a new RAG driver

		cur.execute("INSERT INTO sessions(id, issued_when) VALUES(?, ?)", (sess_id, str(datetime.now())))
		conn.commit()


	conn.close()

	if len(dat) == 0:
		return True
	else:
		return False


# check if the session exists
def does_session_exist(sess_id: int) -> bool:
	conn = sqlite3.connect(config.SESSIONS_DB_PATH)
	cur = conn.cursor()

	cur.execute("DELETE FROM sessions WHERE issued_when < ?", (str(datetime.now() - timedelta(seconds=config.SESSION_LIFETIME)),))
	conn.commit()

	cur.execute("SELECT * FROM sessions WHERE id = ?", (sess_id,))
	dat = cur.fetchall()
	conn.close()

	if len(dat) == 0:
		return False
	else:
		return True


# invalidate and remove a session
def invalidate_session(sess_id: int):
	conn = sqlite3.connect(config.SESSIONS_DB_PATH)
	cur = conn.cursor()

	# clean up a RAG driver associated with this session id
	rag_drivers.pop(sess_id)

	cur.execute("DELETE FROM sessions WHERE id < ?", (sess_id,))
	conn.commit()
	conn.close()
	

class RAGDriver:
	def __init__(self):
		pass
	
	def add_doc(self, doc):
		pass
