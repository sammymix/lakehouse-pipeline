from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from query_engine import question_to_sql, run_sql, summarize_results

app = FastAPI(title="Data Pipeline AI Assistant")

class Question(BaseModel):
    question: str

@app.post("/ask")
def ask(payload: Question):
    try:
        # Step 1: convert question to SQL
        sql = question_to_sql(payload.question)

        # Step 2: run SQL against your real data
        columns, rows = run_sql(sql)

        # Step 3: explain results in plain English
        answer = summarize_results(payload.question, sql, columns, rows)

        return {
            "question": payload.question,
            "sql":      sql,
            "rows":     [dict(zip(columns, row)) for row in rows],
            "answer":   answer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}