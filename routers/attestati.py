from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import db, calc_scadenza, calc_stato

router = APIRouter(prefix="/attestati", tags=["Attestati"])

STATI_SPECIALI = {"nis", "iaa", "iac", "nd"}


class AttestatoIn(BaseModel):
    dipendente_id: int
    tipo_formazione_id: int
    data_esecuzione: str
    stato: str = "valido"          # può essere sovrascritto se speciale
    ente_formatore: str | None = None
    note: str | None = None


@router.get("/")
def list_attestati(
    dipendente_id: int | None = Query(None),
    cantiere_id: int | None = Query(None),
    stato: str | None = Query(None),
    scadenza_entro_giorni: int | None = Query(None),
    categoria: str | None = Query(None),
):
    sql = "SELECT * FROM v_attestati WHERE 1=1"
    params: list = []

    if dipendente_id:
        sql += " AND rowid IN (SELECT id FROM attestati WHERE dipendente_id=?)"
        params.append(dipendente_id)
    if cantiere_id:
        sql += " AND cantiere IN (SELECT nome FROM cantieri WHERE id=?)"
        params.append(cantiere_id)
    if stato:
        sql += " AND stato=?"
        params.append(stato)
    if scadenza_entro_giorni is not None:
        sql += " AND giorni_alla_scadenza IS NOT NULL AND giorni_alla_scadenza <= ?"
        params.append(scadenza_entro_giorni)
    if categoria:
        sql += " AND categoria=?"
        params.append(categoria)

    sql += " ORDER BY giorni_alla_scadenza NULLS LAST, dipendente"

    with db() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/scadenze")
def scadenze_imminenti(giorni: int = Query(90)):
    with db() as con:
        rows = con.execute(
            "SELECT * FROM v_scadenze_imminenti WHERE giorni_alla_scadenza <= ?",
            (giorni,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{att_id}")
def get_attestato(att_id: int):
    with db() as con:
        row = con.execute(
            "SELECT * FROM attestati WHERE id=?", (att_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Attestato non trovato")
    return dict(row)


@router.post("/", status_code=201)
def create_attestato(body: AttestatoIn):
    with db() as con:
        tf = con.execute(
            "SELECT periodicita_anni FROM tipi_formazione WHERE id=?",
            (body.tipo_formazione_id,),
        ).fetchone()
        if not tf:
            raise HTTPException(404, "Tipo formazione non trovato")

        # stato speciale passa diretto, altrimenti calcola da scadenza
        if body.stato.lower() in STATI_SPECIALI:
            scadenza = None
            stato = body.stato.lower()
        else:
            scadenza = calc_scadenza(body.data_esecuzione, tf["periodicita_anni"])
            stato = calc_stato(scadenza)

        cur = con.execute(
            """INSERT INTO attestati
               (dipendente_id, tipo_formazione_id, data_esecuzione,
                data_scadenza, stato, ente_formatore, note)
               VALUES (?,?,?,?,?,?,?)""",
            (body.dipendente_id, body.tipo_formazione_id, body.data_esecuzione,
             scadenza, stato, body.ente_formatore, body.note),
        )
    return {"id": cur.lastrowid, "data_scadenza": scadenza, "stato": stato}


@router.put("/{att_id}")
def update_attestato(att_id: int, body: AttestatoIn):
    with db() as con:
        tf = con.execute(
            "SELECT periodicita_anni FROM tipi_formazione WHERE id=?",
            (body.tipo_formazione_id,),
        ).fetchone()
        if not tf:
            raise HTTPException(404, "Tipo formazione non trovato")

        if body.stato.lower() in STATI_SPECIALI:
            scadenza = None
            stato = body.stato.lower()
        else:
            scadenza = calc_scadenza(body.data_esecuzione, tf["periodicita_anni"])
            stato = calc_stato(scadenza)

        con.execute(
            """UPDATE attestati SET
               dipendente_id=?, tipo_formazione_id=?, data_esecuzione=?,
               data_scadenza=?, stato=?, ente_formatore=?, note=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (body.dipendente_id, body.tipo_formazione_id, body.data_esecuzione,
             scadenza, stato, body.ente_formatore, body.note, att_id),
        )
    return {"id": att_id, "data_scadenza": scadenza, "stato": stato}


@router.delete("/{att_id}", status_code=204)
def delete_attestato(att_id: int):
    with db() as con:
        con.execute("DELETE FROM attestati WHERE id=?", (att_id,))
