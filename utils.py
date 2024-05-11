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
import json


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


# initialize a llm drivers database and a session database
def init_storage():
	with sqlite3.connect(config.SESSIONS_DB_PATH) as conn:
		cur = conn.cursor()
		cur.execute("""
			CREATE TABLE IF NOT EXISTS sessions(
				id INTEGER PRIMARY KEY,
				issued_when TEXT NOT NULL
			)
		""")
		conn.commit()

	with sqlite3.connect(config.LLM_DRIVERS_DB_PATH) as conn:
		cur = conn.cursor()
		cur.execute("""
			CREATE TABLE IF NOT EXISTS llm_drivers(
				id INTEGER PRIMARY KEY,
				uri TEXT NOT NULL,
				type TEXT NOT NULL,
				idle INTEGER NOT NULL
			)
		""")
		cur.execute('INSERT INTO llm_drivers(uri, type, idle) values(?, ?, ?)', ('http://localhost:11434/api/generate', 'local', 1))
		cur.execute('INSERT INTO llm_drivers(uri, type, idle) values(?, ?, ?)', (config.OPENAI_TOKEN, 'openai', 1))
		conn.commit()


# validate llms if they are invalidated
def reset_llms():
	with sqlite3.connect(config.LLM_DRIVERS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('UPDATE llm_drivers SET idle = 1')
		conn.commit()
	

# initialize session
def init_session(sess_id: int) -> bool:
	with sqlite3.connect(config.SESSIONS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('DELETE FROM sessions WHERE issued_when < ?', (str(datetime.now() - timedelta(seconds=config.SESSION_LIFETIME)),))
		conn.commit()

		cur.execute('SELECT * FROM sessions WHERE id = ?', (sess_id,))
		dat = cur.fetchall()

		# if not found, initialize a new session with sess_id
		if len(dat) == 0:
			# clean up a RAG driver previously associated with this session id
			rag_drivers.pop(sess_id, None) 
			rag_drivers[sess_id] = RAGDriver(rag_embedding_model)

			cur.execute('INSERT INTO sessions(id, issued_when) VALUES(?, ?)', (sess_id, str(datetime.now())))
			conn.commit()

		if len(dat) == 0 and rag_drivers.get(sess_id, None) != None:
			return True
		else:
			return False


# check if the session exists
def does_session_exist(sess_id: int) -> bool:
	with sqlite3.connect(config.SESSIONS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('DELETE FROM sessions WHERE issued_when < ?', (str(datetime.now() - timedelta(seconds=config.SESSION_LIFETIME)),))
		conn.commit()

		cur.execute('SELECT * FROM sessions WHERE id = ?', (sess_id,))
		dat = cur.fetchall()

		if len(dat) == 0 or rag_drivers.get(sess_id, None) == None:
			return False
		else:
			return True


# invalidate and remove a session
def invalidate_session(sess_id: int):
	with sqlite3.connect(config.SESSIONS_DB_PATH) as conn:
		cur = conn.cursor()

		# clean up a RAG driver associated with this session id
		rag_drivers.pop(sess_id, None)

		cur.execute('DELETE FROM sessions WHERE id < ?', (sess_id,))
		conn.commit()


# get an available LLM driver
def get_available_llm():
	with sqlite3.connect(config.LLM_DRIVERS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('SELECT id, uri, type FROM llm_drivers WHERE idle = 1')
		dat = cur.fetchone()

		return dat


# invalidate an LLM driver
def invalidate_llm(id):
	with sqlite3.connect(config.LLM_DRIVERS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('UPDATE llm_drivers SET idle = 0 WHERE id = ?', (id, ))
		conn.commit()


# validate an LLM driver
def validate_llm(id):
	with sqlite3.connect(config.LLM_DRIVERS_DB_PATH) as conn:
		cur = conn.cursor()

		cur.execute('UPDATE llm_drivers SET idle = 1 WHERE id = ?', (id, ))
		conn.commit()


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

		llm = get_available_llm()

		output = ''
		if llm != None:
			invalidate_llm(llm[0])

			try:
				output = self.llm.query(template=template, url_token=llm[1], llm_type=llm[2], **args)
			except:
				return json.dumps({'response': '#', 'done': True}, ensure_ascii=False)
			finally:
				validate_llm(llm[0])
		else:
			return json.dumps({'response': '#', 'done': True}, ensure_ascii=False)

		try:
			if lang == 'en':
				raise Exception()

			output = json.loads(output)
			output['response'] = GoogleTranslator(source='en', target=lang).translate(output['response'][:4999])
			output = json.dumps(output, ensure_ascii=False)
		except:
			pass
		finally:
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

		llm = get_available_llm()

		output = ''
		if llm != None:
			invalidate_llm(llm[0])

			try:
				for output in self.llm.squery(template=template, url_token=llm[1], llm_type=llm[2], **args):
					invalidate_llm(llm[0])
					validate_llm(llm[0])
					yield output
			except:
				yield json.dumps({'response': '#', 'done': True}, ensure_ascii=False)
			finally:
				validate_llm(llm[0])
		else:
			yield json.dumps({'response': '#', 'done': True}, ensure_ascii=False)

	
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

		llm = get_available_llm()

		output = ''
		if llm != None:
			invalidate_llm(llm[0])

			try:
				output = await self.llm.aquery(template=template, async_requests=async_requests, url_token=llm[1], llm_type=llm[2], **args)
			except:
				return json.dumps({'response': '#', 'done': True}, ensure_ascii=False)
			finally:
				validate_llm(llm[0])
		else:
			return json.dumps({'response': '#', 'done': True}, ensure_ascii=False)

		try:
			if lang == 'en':
				raise Exception()
			
			output = json.loads(output)
			output['response'] = GoogleTranslator(source='en', target=lang).translate(output['response'][:4999])
			output = json.dumps(output, ensure_ascii=False)
		except:
			pass
		finally:
			return output
