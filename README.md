# HFFRAG API

HFFRAG API is an API implementation based on FastAPI and multithreading for the `HFFRAG` - RAG (Retrieval Augmented Generation) mechanism using `HuggingFace` sentence transformers and `Faiss` similarity search algorithm.

The `HFFRAG` project is hosted on GitHub and is available at: [HFFRAG GitHub Repository](https://github.com/venturestranger/hffrag)

## Installation
To install all the necessary libraries, use the following command:
```bash
pip install -r requirements.txt; git clone https://github.com/venturestranger/hffrag
```

## Setup
To start the application in development mode, use the following command:
```bash
python api.py
```
To start the application in production mode, use the following command:
```bash
gunicorn -w <NUMBER OF THREADS> -k uvicorn.workers.UvicornWorker -b 0.0.0.0:<PORT> api:gunicorn_factory
```

## Routing
- `/sales/api/rest/v1/doc` `POST` - Adds a document to the user's RAG driver indexer (either a text document `content` or URL `url` to the website from which content will be scraped).
```json
{
    "url": "https://en.wikipedia.org/wiki/Schizophrenia"
}
```
```json
{
    "content": "Schizophrenia is a mental disorder characterized by reoccurring episodes of psychosis..."
}
```
---

- `/sales/api/rest/v1/prompt` `POST` - Prompts an LLM with given `queries` and `top`, specifying a number of retrieved documents used for output generation (the more the values is, the more accurate answers it will generate, but might not fit the context window length). 

`queries` should be a non-empty list of strings. `top` should be a non-zero integer number.
```json
{
    "queries": ["What social problems are commonly correlated with schizophrenia?", "How can schizophrenia be cured?"],
    "top": 10
}
```
`context` is an optional field that provides the system with more context information that might be helpful for output generation. The field should be a non-empty list of strings.
```json
{
    "queries": ["What do people with schizophrenia experience?"],
    "context": ["Depending on type of schizophrenia, people with schizophrenia experience ..."]
}
```
`lang` is another optional field that identifies what language is used for `quries` and `context` fields. It might be important to specify when non-English queries attempt to prompt an LLM that was majorly trained on English text corpora.
```json
{
    "queries": ["Какие недуги переживают люди с шизофренией?"],
    "top": 10,
    "context": ["В зависимости от типа шизофрении, спект переживаемого опыта может ..."],
    "lang": "ru"
}
```
---

- `/sales/api/rest/v1/auth` `GET` - Initializes a user session, RAG driver on the server side, and returns a session token, authorizing the user to perform server-side actions. Requires `key` parameter to obtain an API access.
```
[GET] /sales/api/rest/v1/auth?key=admin123 ->

HTTP 200:
eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzZXJ2ZXIiLCJzZXNzX2lkIjoyMjM0NzIxMDYxNTUxMzYzfQ.FzaeHugT0SrAGraLvopFmEV3D_nU_qQz5pnhgGq440rrcXOlBsQuXip2OQ0ppQq7qD5TD5cB-xwH5be1t3LaxA
```

Once the token is obtained, it should be used in the `Authorization` header, followed by `Bearer`.
```bash
"Authorization": "Bearer eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzZXJ2ZXIiLCJzZXNzX2lkIjoyMjM0NzIxMDYxNTUxMzYzfQ.FzaeHugT0SrAGraLvopFmEV3D_nU_qQz5pnhgGq440rrcXOlBsQuXip2OQ0ppQq7qD5TD5cB-xwH5be1t3LaxA"
```

---
