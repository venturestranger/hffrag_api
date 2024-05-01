from config import configs
from datetime import datetime
from datetime import timedelta
from sentence_transformers import SentenceTransformer
from deep_translator import GoogleTranslator
from hffrag import Indexer, Templater, Driver
from pydantic import BaseModel
from aiohttp import ClientSession
from aiohttp.web import Response
import sqlite3


config = configs['default']
rag_embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
rag_drivers = {}


# prompt document upload
class Document(BaseModel):
	content: str | None = None
	url: str | None = None


# prompt document upload
class Query(BaseModel):
	queries: list | None = []
	context: list | None = []
	top: int | None = 1
	lang: str | None = 'en'
	stream: bool | None = False


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
		rag_drivers.pop(sess_id, None) 
		rag_drivers[sess_id] = RAGDriver(rag_embedding_model)

		cur.execute("INSERT INTO sessions(id, issued_when) VALUES(?, ?)", (sess_id, str(datetime.now())))
		conn.commit()


	conn.close()

	if len(dat) == 0 and rag_drivers.get(sess_id, None) != None:
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

	if len(dat) == 0 or rag_drivers.get(sess_id, None) == None:
		return False
	else:
		return True


# invalidate and remove a session
def invalidate_session(sess_id: int):
	conn = sqlite3.connect(config.SESSIONS_DB_PATH)
	cur = conn.cursor()

	# clean up a RAG driver associated with this session id
	rag_drivers.pop(sess_id, None)

	cur.execute("DELETE FROM sessions WHERE id < ?", (sess_id,))
	conn.commit()
	conn.close()
	

# asynchronous http client
class Arequests:
	def __init__(self):
		pass
	
	async def get(self, url: str) -> Response:
		async with ClientSession(trust_env=True) as session:
			return await session.get(url)

	async def post(self, url: str, json: dict) -> Response:
		async with ClientSession(trust_env=True) as session:
			return await session.post(url, json=json)


# personalized rag driver for each connection
class RAGDriver:
	def __init__(self, embedding: SentenceTransformer = None):
		if embedding == None:
			self.indexer = Indexer()
		else:
			self.indexer = Indexer(embedding=embedding)

		self.llm = Driver()
	
	# synchronously prompt LLM
	def prompt(self, queries: list, context: list, top: int, lang: str = 'en') -> str:
		msgs = [
			('system', 'Geven that: '),
		]
		args = {}

		if lang != 'en':
			for i in range(len(context)):
				try:
					context[i] = GoogleTranslator(source=lang, target='en').translate(context[i][:4999])
				except:
					pass
				
			for i in range(len(queries)):
				try:
					queries[i] = GoogleTranslator(source=lang, target='en').translate(queries[i][:4999])
				except:
					pass

		for query in context:
			msgs.append(('system', query))

		for query in range(len(queries)):
			relevant = self.indexer.search(queries[query], top=top)

			for i in range(top):
				if relevant[i] == -1:
					break

				arg = f'query_{query}_{i}'
				args[arg] = self.indexer.retrieve(relevant[i])[1]
				msgs.append(('system', '{' + arg + '}'))

		msgs.append(('system', 'Answer the following: '))

		for query in range(len(queries)):
			arg = f'query_{query}'
			args[arg] = queries[query]
			msgs.append(('human', '{' + arg + '}'))

		template = Templater(msgs)

		output = self.llm.query(template=template, **args)
		try:
			if lang == 'en':
				raise Exception()
			return GoogleTranslator(source='en', target=lang).translate(output[:4999])
		except:
			return output

	# synchronously prompt LLM with streaming
	def sprompt(self, queries: list, context: list, top: int, lang: str = 'en') -> str:
		msgs = [
			('system', 'Geven that: '),
		]
		args = {}

		if lang != 'en':
			for i in range(len(context)):
				try:
					context[i] = GoogleTranslator(source=lang, target='en').translate(context[i][:4999])
				except:
					pass
				
			for i in range(len(queries)):
				try:
					queries[i] = GoogleTranslator(source=lang, target='en').translate(queries[i][:4999])
				except:
					pass

		for query in context:
			msgs.append(('system', query))

		for query in range(len(queries)):
			relevant = self.indexer.search(queries[query], top=top)

			for i in range(top):
				if relevant[i] == -1:
					break

				arg = f'query_{query}_{i}'
				args[arg] = self.indexer.retrieve(relevant[i])[1]
				msgs.append(('system', '{' + arg + '}'))

		msgs.append(('system', 'Answer the following: '))

		for query in range(len(queries)):
			arg = f'query_{query}'
			args[arg] = queries[query]
			msgs.append(('human', '{' + arg + '}'))

		template = Templater(msgs)

		for output in self.llm.squery(template=template, **args):
			yield output
	
	# asynchronously prompt LLM
	async def aprompt(self, queries: list, context: list, top: int, async_requests: Arequests, lang: str = 'en') -> str:
		msgs = [
			('system', 'You know: '),
		]
		args = {}

		if lang != 'en':
			for i in range(len(context)):
				try:
					context[i] = GoogleTranslator(source=lang, target='en').translate(context[i][:4999])
				except:
					pass
				
			for i in range(len(queries)):
				try:
					queries[i] = GoogleTranslator(source=lang, target='en').translate(queries[i][:4999])
				except:
					pass

		for query in context:
			msgs.append(('system', query))

		for query in range(len(queries)):
			relevant = self.indexer.search(queries[query], top=top)

			for i in range(top):
				if relevant[i] == -1:
					break

				arg = f'query_{query}_{i}'
				args[arg] = self.indexer.retrieve(relevant[i])[1]
				msgs.append(('system', '{' + arg + '}'))

		msgs.append(('system', 'Answer the following:'))

		for query in range(len(queries)):
			arg = f'query_{query}'
			args[arg] = queries[query]
			msgs.append(('human', '{' + arg + '}'))

		template = Templater(msgs)

		output = await self.llm.aquery(template=template, async_requests=async_requests, **args)
		try:
			if lang == 'en':
				raise Exception()
			return GoogleTranslator(source='en', target=lang).translate(output[:4999])
		except:
			return output
