import json
import os
from datetime import date, datetime, timedelta, timezone

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from rules import aux_batch_error, freeze_aux_batch, judge

SECRET = os.environ.get("JWT_SECRET", "herb-process-dev-secret")
DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54393/herb")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
USERS = {
    "processor": {"role": "writer", "password_hash": pwd.hash("herb123456")},
    "checker": {"role": "reader", "password_hash": pwd.hash("check123456")},
}


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class StepIn(BaseModel):
    name: str
    temp_c: float
    minutes: float


class BatchIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    aux_batch_id: int | None = None
    steps: list[StepIn]


class AuxBatchIn(BaseModel):
    material: str = Field(min_length=1, max_length=80)
    lot_no: str = Field(min_length=1, max_length=80)
    expires_on: date


class AuxBatchPatchIn(BaseModel):
    expires_on: date


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=401, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "writer":
        raise HTTPException(status_code=403, detail="仅炮制员可写入记录")
    return user


app = FastAPI(title="饮片炮制记录台")


@app.on_event("startup")
def startup():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                verdict text NOT NULL,
                reason text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS aux_batches (
                id serial PRIMARY KEY,
                material text NOT NULL,
                lot_no text NOT NULL,
                expires_on date NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]
        if count == 0:
            now = datetime.now(timezone.utc)
            samples = [
                ("甘草", {"steps": [{"name": "清炒", "temp_c": 120, "minutes": 12}]}),
                ("黄芩", {"steps": [{"name": "清炒", "temp_c": 40, "minutes": 12}]}),
            ]
            for herb, doc in samples:
                verdict, reason = judge(doc)
                conn.execute(
                    """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
                       VALUES (%s, %s::jsonb, %s, %s, %s, %s)""",
                    (herb, json.dumps(doc, ensure_ascii=False), verdict, reason, "processor", now),
                )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "herb-process-record"}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = USERS.get(body.username.strip())
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": body.username.strip(), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")
    return {"access_token": token, "username": body.username.strip(), "role": user["role"]}


@app.get("/api/batches")
def list_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute("SELECT id, herb, doc, verdict, reason, created_by FROM batches ORDER BY id DESC").fetchall()
    return rows


@app.get("/api/aux-batches")
def list_aux_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, material, lot_no, expires_on, created_by FROM aux_batches ORDER BY id DESC"
        ).fetchall()
    return rows


@app.post("/api/aux-batches", status_code=201)
def create_aux_batch(body: AuxBatchIn, user: dict = Depends(require_writer)):
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO aux_batches (material, lot_no, expires_on, created_by, created_at)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, material, lot_no, expires_on, created_by""",
            (
                body.material.strip(),
                body.lot_no.strip(),
                body.expires_on,
                user["username"],
                datetime.now(timezone.utc),
            ),
        ).fetchone()
        conn.commit()
    return row


@app.patch("/api/aux-batches/{aux_id}")
def patch_aux_batch(aux_id: int, body: AuxBatchPatchIn, _user: dict = Depends(require_writer)):
    # 只改正册上失效日；batches.doc 里已冻结的批号正文不动。
    with connect() as conn:
        row = conn.execute(
            """UPDATE aux_batches SET expires_on = %s
               WHERE id = %s
               RETURNING id, material, lot_no, expires_on, created_by""",
            (body.expires_on, aux_id),
        ).fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status_code=404, detail="批号册中没有这条记录")
    return row


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    if body.aux_batch_id is None:
        raise HTTPException(status_code=400, detail="缺选辅料批号：写清炒文书必须从批号册点选辅料批号")
    with connect() as conn:
        aux = conn.execute(
            "SELECT id, material, lot_no, expires_on FROM aux_batches WHERE id = %s",
            (body.aux_batch_id,),
        ).fetchone()
        problem = aux_batch_error(aux, date.today())
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        doc = {
            "steps": [s.model_dump() for s in body.steps],
            "aux_batch": freeze_aux_batch(aux),
        }
        verdict, reason = judge(doc)
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row
