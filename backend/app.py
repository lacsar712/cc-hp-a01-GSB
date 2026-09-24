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

from rules import judge

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
    steps: list[StepIn]
    excipient_id: int | None = None


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    lot_no: str = Field(min_length=1, max_length=80)
    expires_on: date


class ExpiryIn(BaseModel):
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
            """CREATE TABLE IF NOT EXISTS excipient_lots (
                id serial PRIMARY KEY,
                name text NOT NULL,
                lot_no text NOT NULL,
                expires_on date NOT NULL,
                registered_by text NOT NULL,
                registered_at timestamptz NOT NULL,
                UNIQUE (name, lot_no)
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


@app.get("/api/excipient-lots")
def list_lots(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, name, lot_no, expires_on, registered_by
               FROM excipient_lots ORDER BY id DESC"""
        ).fetchall()
    today = date.today()
    for row in rows:
        row["expires_on"] = row["expires_on"].isoformat()
        row["expired"] = row["expires_on"] < today.isoformat()
    return rows


@app.post("/api/excipient-lots", status_code=201)
def register_lot(body: RegisterIn, user: dict = Depends(require_writer)):
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM excipient_lots WHERE name = %s AND lot_no = %s",
            (body.name.strip(), body.lot_no.strip()),
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="该辅料批号已在册")
        row = conn.execute(
            """INSERT INTO excipient_lots (name, lot_no, expires_on, registered_by, registered_at)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, name, lot_no, expires_on, registered_by""",
            (body.name.strip(), body.lot_no.strip(), body.expires_on,
             user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    row["expires_on"] = row["expires_on"].isoformat()
    row["expired"] = row["expires_on"] < date.today().isoformat()
    return row


@app.patch("/api/excipient-lots/{lot_id}")
def update_lot_expiry(lot_id: int, body: ExpiryIn, user: dict = Depends(require_writer)):
    with connect() as conn:
        row = conn.execute(
            """UPDATE excipient_lots SET expires_on = %s
               WHERE id = %s
               RETURNING id, name, lot_no, expires_on, registered_by""",
            (body.expires_on, lot_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="批号不存在")
        conn.commit()
    row["expires_on"] = row["expires_on"].isoformat()
    row["expired"] = row["expires_on"] < date.today().isoformat()
    return row


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    # 先建册、再开炒：批号必须从册中点选
    if body.excipient_id is None:
        raise HTTPException(status_code=400, detail="缺选辅料批号：请从批号册中点选未失效批号")
    with connect() as conn:
        lot = conn.execute(
            "SELECT id, name, lot_no, expires_on FROM excipient_lots WHERE id = %s",
            (body.excipient_id,),
        ).fetchone()
        if lot is None:
            raise HTTPException(status_code=400, detail="缺选辅料批号：所选批号不在册中")
        # 已过失效日一律拒写；按开炒当日判定
        if lot["expires_on"] < date.today():
            raise HTTPException(
                status_code=400,
                detail=f"辅料批号已过期：{lot['name']} {lot['lot_no']} 失效日 {lot['expires_on'].isoformat()}",
            )
        # 批号正文随文书冻结：记录开炒当时的批号与失效日，事后改册不回写
        doc = {
            "steps": [s.model_dump() for s in body.steps],
            "excipient": {
                "lot_id": lot["id"],
                "name": lot["name"],
                "lot_no": lot["lot_no"],
                "expires_on": lot["expires_on"].isoformat(),
            },
        }
        verdict, reason = judge(doc)
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason,
             user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row
