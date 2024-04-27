from fastapi import Request, Response
from utils import does_session_exist, config
import jwt


# check if token is valid
async def auth_middleware_v1(request: Request, handler):
	token = request.headers.get('Authorization', 'Bearer _')
	token = token.split()[1]

	try:
		payload = jwt.decode(token, config.SECRET_KEY, algorithms=['HS512'])
	except:
		return Response(content='Unauthorized', status_code=401)
	else:
		if payload.get('iss', None) == config.ISSUER and payload.get('sess_id', None) != None:
			# if token is valid, pass the retrieved session id to further calls
			if does_session_exist(payload['sess_id']):
				request.state.id = payload['sess_id']
				return await handler(request)
			else:
				return Response(content='Gone', status_code=410)
		else:
			return Response(content='Unauthorized', status_code=401)
