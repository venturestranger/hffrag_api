from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from middlewares import auth_middleware_v1
from handlers import doc_post_v1, prompt_post_v1, auth_get_v1
from utils import config, reset_llms, Document, Query


app = FastAPI()
APIv1 = FastAPI()


@APIv1.post('/doc')
async def _doc_post_v1(document: Document, request: Request):
	return await doc_post_v1(document, request)


@APIv1.post('/prompt')
async def _prompt_post_v1(query: Query, request: Request):
	return await prompt_post_v1(query, request)


@APIv1.middleware('http')
async def _auth_middleware_v1(request: Request, handler):
	return await auth_middleware_v1(request, handler)


@app.get('/sales/api/rest/v1/auth')
async def _auth_get_v1(request: Request):
	return auth_get_v1(request)


app.mount('/sales/api/rest/v1', APIv1)
app.add_middleware(
	CORSMiddleware,
	allow_origins=['*'],
	allow_credentials=True,
	allow_methods=['*'],
	allow_headers=['*']
)


if __name__ == '__main__':
	reset_llms()

	import uvicorn
	uvicorn.run(app, host='0.0.0.0', port=config.PORT)


async def gunicorn_factory():
	reset_llms()

	return app

