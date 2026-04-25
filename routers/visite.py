from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, model_validator, Field
from database import db, calc_scadenza_mesi, calc_stato

router = APIRouter(prefix="/visite", tags=["Visite Mediche"])

# Durate predefinite in mesi per ogni tipo.
# Il medico può sempre sovrascrivere con qualsiasi valore (durata_mesi).
DURATE_DEFAULT: dict[str, int | None] = {
    "annuale":        12,
    "semestrale":      6,
    "trimestrale":     3,
    "quinquennale":   60,
    "biennale":       24,
    "straordinaria":  None,   # nessuna scadenza automatica
    "personalizzata": None,   # durata_mesi obbligatorio
}


class VisitaIn(BaseModel):
    dipendente_id: int
    data_visita: str

    tipo: str = Field(
        default="annuale",
        description=(
            "Tipo visita: annuale | semestrale | trimestrale | "
            "quinquennale | biennale | straordinaria | personalizzata"
        ),
    )
    # Se valorizzato sovrascrive il default del tipo.
    # Es: tipo=annuale ma durata_mesi=3 → scadenza a 3 mesi (prescrizione medica).
    durata_mesi: int | None = Field(
        default=None,
        ge=1,
        le=120,
        description="Durata in mesi fino alla prossima visita (1-120).",
    )
    esito: str = Field(
        default="idoneo",
        description="idoneo | idoneo_limitazioni | non_idoneo | in_attesa",
    )
    medico: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def resolve_durata(self) -> "VisitaIn":
        if self.durata_mesi is None:
            self.durata_mesi = DURATE_DEFAULT.get(self.tipo)
        if self.tipo == "personalizzata" and self.durata_mesi is None:
            raise ValueError(
                "Per tipo 'personalizzata' è obbligatorio specificare durata_mesi."
            )
        return self


def _build_response(row_id: int, data_visita: str, durata_mesi: int | None) -> dict:
    scadenza = calc_scadenza_mesi(data_visita, durata_mesi)
    return {
        "id": row_id,
        "data_scadenza": scadenza,
        "durata_mesi": durata_mesi,
        "stato": calc_stato(scadenza),
    }


@router.get("/")
def list_visite(
    dipendente_id: int | None = Query(None),
    cantiere_id: int | None = Query(None),
    scadenza_entro_giorni: int | None = Query(None),
    esito: str | None = Query(None),
):
    sql = "SELECT * FROM v_visite WHERE 1=1"
    params: list = []
    if dipendente_id:
        sql += " AND rowid IN (SELECT id FROM visite_mediche WHERE dipendente_id=?)"
        params.append(dipendente_id)
    if cantiere_id:
        sql += " AND cantiere IN (SELECT nome FROM cantieri WHERE id=?)"
        params.append(cantiere_id)
    if scadenza_entro_giorni is not None:
        sql += " AND giorni_alla_scadenza IS NOT NULL AND giorni_alla_scadenza <= ?"
        params.append(scadenza_entro_giorni)
    if esito:
        sql += " AND esito=?"
        params.append(esito)
    sql += " ORDER BY giorni_alla_scadenza NULLS LAST, dipendente"
    with db() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/tipi")
def tipi_visita():
    """Restituisce i tipi di visita con la durata predefinita in mesi."""
    return [
        {"tipo": k, "durata_mesi_default": v}
        for k, v in DURATE_DEFAULT.items()
    ]


@router.get("/{visita_id}")
def get_visita(visita_id: int):
    with db() as con:
        row = con.execute(
            "SELECT * FROM visite_mediche WHERE id=?", (visita_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Visita non trovata")
    return dict(row)


@router.post("/", status_code=201)
def create_visita(body: VisitaIn):
    scadenza = calc_scadenza_mesi(body.data_visita, body.durata_mesi)
    with db() as con:
        cur = con.execute(
            """INSERT INTO visite_mediche
               (dipendente_id, data_visita, data_scadenza, tipo,
                durata_mesi, esito, medico, note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (body.dipendente_id, body.data_visita, scadenza,
             body.tipo, body.durata_mesi,
             body.esito, body.medico, body.note),
        )
    return _build_response(cur.lastrowid, body.data_visita, body.durata_mesi)


@router.put("/{visita_id}")
def update_visita(visita_id: int, body: VisitaIn):
    scadenza = calc_scadenza_mesi(body.data_visita, body.durata_mesi)
    with db() as con:
        con.execute(
            """UPDATE visite_mediche SET
               dipendente_id=?, data_visita=?, data_scadenza=?,
               tipo=?, durata_mesi=?, esito=?, medico=?, note=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (body.dipendente_id, body.data_visita, scadenza,
             body.tipo, body.durata_mesi,
             body.esito, body.medico, body.note, visita_id),
        )
    return _build_response(visita_id, body.data_visita, body.durata_mesi)


@router.delete("/{visita_id}", status_code=204)
def delete_visita(visita_id: int):
    with db() as con:
        con.execute("DELETE FROM visite_mediche WHERE id=?", (visita_id,))
