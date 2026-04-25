from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/tipi-formazione", tags=["Catalogo Corsi"])


class TipoFormazioneIn(BaseModel):
    codice: str
    nome: str
    riferimento_normativo: str | None = None
    durata_ore: int | None = None
    periodicita_anni: int | None = None
    categoria: str = "formazione"
    attivo: int = 1
    note: str | None = None


@router.get("/")
def list_tipi(categoria: str | None = None):
    sql = "SELECT * FROM tipi_formazione WHERE attivo=1"
    params: list = []
    if categoria:
        sql += " AND categoria=?"
        params.append(categoria)
    sql += " ORDER BY categoria, nome"
    with db() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/categorie")
def list_categorie():
    with db() as con:
        rows = con.execute(
            "SELECT DISTINCT categoria FROM tipi_formazione WHERE attivo=1 ORDER BY categoria"
        ).fetchall()
    return [r[0] for r in rows]


@router.get("/{tf_id}")
def get_tipo(tf_id: int):
    with db() as con:
        row = con.execute(
            "SELECT * FROM tipi_formazione WHERE id=?", (tf_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Tipo formazione non trovato")
    return dict(row)


@router.post("/", status_code=201)
def create_tipo(body: TipoFormazioneIn):
    with db() as con:
        cur = con.execute(
            """INSERT INTO tipi_formazione
               (codice, nome, riferimento_normativo, durata_ore,
                periodicita_anni, categoria, attivo, note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (body.codice.upper(), body.nome, body.riferimento_normativo,
             body.durata_ore, body.periodicita_anni, body.categoria,
             body.attivo, body.note),
        )
    return {"id": cur.lastrowid, **body.model_dump()}


@router.put("/{tf_id}")
def update_tipo(tf_id: int, body: TipoFormazioneIn):
    with db() as con:
        con.execute(
            """UPDATE tipi_formazione SET codice=?, nome=?, riferimento_normativo=?,
               durata_ore=?, periodicita_anni=?, categoria=?, attivo=?, note=?
               WHERE id=?""",
            (body.codice.upper(), body.nome, body.riferimento_normativo,
             body.durata_ore, body.periodicita_anni, body.categoria,
             body.attivo, body.note, tf_id),
        )
    return {"id": tf_id, **body.model_dump()}
