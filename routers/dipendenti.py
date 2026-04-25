from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/dipendenti", tags=["Dipendenti"])


class DipendentIn(BaseModel):
    cantiere_id: int
    cognome: str
    nome: str
    agenzia: str | None = None
    data_assunzione: str | None = None
    attivo: int = 1
    note: str | None = None


@router.get("/")
def list_dipendenti(
    cantiere_id: int | None = Query(None),
    attivo: int | None = Query(None),
    cerca: str | None = Query(None),
):
    sql = """
        SELECT d.id, d.cognome, d.nome, d.agenzia, d.attivo,
               d.data_assunzione, d.note, c.nome AS cantiere
        FROM dipendenti d
        JOIN cantieri c ON c.id = d.cantiere_id
        WHERE 1=1
    """
    params: list = []
    if cantiere_id is not None:
        sql += " AND d.cantiere_id = ?"
        params.append(cantiere_id)
    if attivo is not None:
        sql += " AND d.attivo = ?"
        params.append(attivo)
    if cerca:
        sql += " AND (d.cognome LIKE ? OR d.nome LIKE ?)"
        params += [f"%{cerca}%", f"%{cerca}%"]
    sql += " ORDER BY d.cognome, d.nome"

    with db() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/{dip_id}")
def get_dipendente(dip_id: int):
    with db() as con:
        row = con.execute(
            """SELECT d.*, c.nome AS cantiere
               FROM dipendenti d JOIN cantieri c ON c.id=d.cantiere_id
               WHERE d.id=?""",
            (dip_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Dipendente non trovato")
    return dict(row)


@router.post("/", status_code=201)
def create_dipendente(body: DipendentIn):
    with db() as con:
        cur = con.execute(
            """INSERT INTO dipendenti
               (cantiere_id, cognome, nome, agenzia, data_assunzione, attivo, note)
               VALUES (?,?,?,?,?,?,?)""",
            (body.cantiere_id, body.cognome.upper(), body.nome.upper(),
             body.agenzia, body.data_assunzione, body.attivo, body.note),
        )
    return {"id": cur.lastrowid, **body.model_dump()}


@router.put("/{dip_id}")
def update_dipendente(dip_id: int, body: DipendentIn):
    with db() as con:
        con.execute(
            """UPDATE dipendenti SET cantiere_id=?, cognome=?, nome=?, agenzia=?,
               data_assunzione=?, attivo=?, note=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (body.cantiere_id, body.cognome.upper(), body.nome.upper(),
             body.agenzia, body.data_assunzione, body.attivo, body.note, dip_id),
        )
    return {"id": dip_id, **body.model_dump()}


@router.delete("/{dip_id}", status_code=204)
def delete_dipendente(dip_id: int):
    with db() as con:
        con.execute("DELETE FROM dipendenti WHERE id=?", (dip_id,))
