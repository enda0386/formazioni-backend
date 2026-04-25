from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/cantieri", tags=["Cantieri"])


class CantierIn(BaseModel):
    nome: str
    descrizione: str | None = None
    attivo: int = 1


@router.get("/")
def list_cantieri():
    with db() as con:
        rows = con.execute(
            "SELECT id, nome, descrizione, attivo FROM cantieri ORDER BY nome"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{cantiere_id}")
def get_cantiere(cantiere_id: int):
    with db() as con:
        row = con.execute(
            "SELECT * FROM cantieri WHERE id = ?", (cantiere_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cantiere non trovato")
    return dict(row)


@router.post("/", status_code=201)
def create_cantiere(body: CantierIn):
    with db() as con:
        cur = con.execute(
            "INSERT INTO cantieri (nome, descrizione, attivo) VALUES (?,?,?)",
            (body.nome, body.descrizione, body.attivo),
        )
    return {"id": cur.lastrowid, **body.model_dump()}


@router.put("/{cantiere_id}")
def update_cantiere(cantiere_id: int, body: CantierIn):
    with db() as con:
        con.execute(
            "UPDATE cantieri SET nome=?, descrizione=?, attivo=? WHERE id=?",
            (body.nome, body.descrizione, body.attivo, cantiere_id),
        )
    return {"id": cantiere_id, **body.model_dump()}


@router.delete("/{cantiere_id}", status_code=204)
def delete_cantiere(cantiere_id: int):
    with db() as con:
        try:
            con.execute("DELETE FROM cantieri WHERE id=?", (cantiere_id,))
        except Exception:
            raise HTTPException(409, "Cantiere in uso: rimuovi prima i dipendenti")
