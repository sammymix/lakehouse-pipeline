import logging
import os
from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from query_engine import question_to_sql, run_sql, summarize_results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Data Pipeline AI Assistant")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_bearer = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(_bearer)):
    if credentials.credentials != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="unauthorized")

class Question(BaseModel):
    question: str

@app.post("/ask")
@limiter.limit("10/minute")
def ask(request: Request, payload: Question, _: None = Security(verify_api_key)):
    if len(payload.question) > 500:
        raise HTTPException(status_code=400, detail="invalid request")

    try:
        sql = question_to_sql(payload.question)
        columns, rows = run_sql(sql)
        answer = summarize_results(payload.question, sql, columns, rows)
        return {
            "question": payload.question,
            "sql":      sql,
            "rows":     [dict(zip(columns, row)) for row in rows],
            "answer":   answer
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid request")
    except RuntimeError:
        raise HTTPException(status_code=500, detail="internal error")
    except Exception:
        logger.exception("Unhandled error in /ask")
        raise HTTPException(status_code=500, detail="internal error")

@app.get("/health")
def health():
    return {"status": "ok"}
