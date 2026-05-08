import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from query_engine import question_to_sql, run_sql, summarize_results

logging.basicConfig(level=logging.INFO)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Data Pipeline AI Assistant")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class Question(BaseModel):
    question: str

@app.post("/ask")
@limiter.limit("10/minute")
def ask(request: Request, payload: Question):
    if len(payload.question) > 500:
        raise HTTPException(status_code=400, detail="Question must be 500 characters or fewer")

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
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logging.getLogger(__name__).exception("Unhandled error in /ask")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
def health():
    return {"status": "ok"}
