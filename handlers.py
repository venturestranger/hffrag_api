from fastapi import Request, Response
from random import randint
from utils import config, init_session, rag_drivers, Arequests, Document, Query
import asyncio
import jwt


async def doc_post_v1(document: Document, request: Request) -> Response:
	if document.url != None:
		await asyncio.to_thread(rag_drivers[request.state.sess_id].indexer.add, url=document.url, label=str(request.state.sess_id))
	elif document.content != None:
		await asyncio.to_thread(rag_drivers[request.state.sess_id].indexer.add, content=document.content, label=str(request.state.sess_id))

	return Response(content='Created', status_code=201)


async def prompt_post_v1(query: Query, request: Request) -> Response:
	if len(query.queries) != 0 and len(query.queries[0]) > 0:
		ret = await rag_drivers[request.state.sess_id].aprompt(query.queries, query.top, Arequests())

		return Response(content=ret, status_code=200)
	else:
		return Response(content="Unprocessable Entity", status_code=422)
	

# generate a token for a user if an access key is right
def auth_get_v1(request: Request) -> Response:
	key = request.query_params.get('key', None)

	if key == config.AUTH_KEY:
		sess_id = randint(0, 9223372036854775)

		if init_session(sess_id) == False:
			return Response(content='Conflict', status_code=409)

		payload = {
			'iss': config.ISSUER,
			'sess_id': sess_id
		}
		token = jwt.encode(payload, config.SECRET_KEY, algorithm='HS512')

		return Response(content=token, status_code=200)
	else:
		return Response(content='Forbidden', status_code=403)
