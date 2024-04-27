from fastapi import Request, Response
from random import randint
from utils import config, init_session
import jwt


async def doc_get_v1(request: Request):
	return Response(content=str(request.state.id), status_code=200)


async def doc_post_v1(request: Request):
	return Response(content='OK', status_code=200)


async def prompt_get_v1(request: Request):
	return Response(content='OK', status_code=200)


def auth_get_v1(request: Request):
	key = request.query_params.get('key', None)

	if key == config.AUTH_KEY:
		sess_id = randint(0, 9223372036854775)

		while init_session(sess_id) == False:
			sess_id = randint(0, 9223372036854775)

		payload = {
			'iss': config.ISSUER,
			'sess_id': sess_id
		}
		token = jwt.encode(payload, config.SECRET_KEY, algorithm='HS512')

		return Response(content=token, status_code=200)
	else:
		return Response(content='Forbidden', status_code=403)
