"""
Cantieri Temporanei — router completo.

Endpoints principali:
  GET/POST/PUT/DELETE  /cantieri-temp/
  GET/POST/DELETE      /cantieri-temp/{id}/dipendenti
  PUT                  /cantieri-temp/{id}/corsi-richiesti
  GET                  /cantieri-temp/{id}/checklist   ← view principale
"""
import json
from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/cantieri-temp", tags=["Cantieri Temporanei"])


# ── Modelli ───────────────────────────────────────────────────────────────────

class CantiereTempIn(BaseModel):
    nome: str
    cliente: str | None = None
    data_inizio: str | None = None
    data_fine: str | None = None
    descrizione: str | None = None
    attivo: int = 1


class AssegnazioneIn(BaseModel):
    dipendente_id: int
    data_ingresso: str | None = None
    note: str | None = None


class CorsiRichiesti(BaseModel):
    """Lista di tipo_formazione_id richiesti per il cantiere (per tutti i dipendenti)."""
    tipo_formazione_ids: list[int]


class CorsiDipendente(BaseModel):
    """Sovrascrittura corsi per uno specifico dipendente nel cantiere."""
    tipo_formazione_ids: list[int]


# ── CRUD Cantieri Temporanei ──────────────────────────────────────────────────

@router.get("/")
def list_cantieri_temp(attivo: int | None = None):
    sql = """
        SELECT ct.*,
               COUNT(ac.id) AS n_dipendenti
        FROM cantieri_temporanei ct
        LEFT JOIN assegnazioni_cantiere ac ON ac.cantiere_temp_id = ct.id
        WHERE 1=1
    """
    params: list = []
    if attivo is not None:
        sql += " AND ct.attivo = ?"
        params.append(attivo)
    sql += " GROUP BY ct.id ORDER BY ct.attivo DESC, ct.data_inizio DESC"
    with db() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/{ct_id}")
def get_cantiere_temp(ct_id: int):
    with db() as con:
        row = con.execute(
            "SELECT * FROM cantieri_temporanei WHERE id=?", (ct_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cantiere temporaneo non trovato")
    return dict(row)


@router.post("/", status_code=201)
def create_cantiere_temp(body: CantiereTempIn):
    with db() as con:
        cur = con.execute(
            """INSERT INTO cantieri_temporanei
               (nome, cliente, data_inizio, data_fine, descrizione, attivo)
               VALUES (?,?,?,?,?,?)""",
            (body.nome, body.cliente, body.data_inizio,
             body.data_fine, body.descrizione, body.attivo),
        )
    return {"id": cur.lastrowid, **body.model_dump()}


@router.put("/{ct_id}")
def update_cantiere_temp(ct_id: int, body: CantiereTempIn):
    with db() as con:
        con.execute(
            """UPDATE cantieri_temporanei SET
               nome=?, cliente=?, data_inizio=?, data_fine=?,
               descrizione=?, attivo=?
               WHERE id=?""",
            (body.nome, body.cliente, body.data_inizio,
             body.data_fine, body.descrizione, body.attivo, ct_id),
        )
    return {"id": ct_id, **body.model_dump()}


@router.delete("/{ct_id}", status_code=204)
def delete_cantiere_temp(ct_id: int):
    with db() as con:
        con.execute("DELETE FROM cantieri_temporanei WHERE id=?", (ct_id,))


# ── Gestione dipendenti assegnati ─────────────────────────────────────────────

@router.get("/{ct_id}/dipendenti")
def list_dipendenti_cantiere(ct_id: int):
    with db() as con:
        rows = con.execute(
            """SELECT ac.id, ac.dipendente_id, ac.corsi_richiesti,
                      ac.data_ingresso, ac.note,
                      d.cognome, d.nome, d.agenzia,
                      c.nome AS cantiere_sede
               FROM assegnazioni_cantiere ac
               JOIN dipendenti d ON d.id = ac.dipendente_id
               JOIN cantieri   c ON c.id = d.cantiere_id
               WHERE ac.cantiere_temp_id = ?
               ORDER BY d.cognome, d.nome""",
            (ct_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["corsi_richiesti"] = json.loads(d["corsi_richiesti"] or "[]")
        result.append(d)
    return result


@router.post("/{ct_id}/dipendenti", status_code=201)
def aggiungi_dipendente(ct_id: int, body: AssegnazioneIn):
    # verifica cantiere esiste
    with db() as con:
        if not con.execute(
            "SELECT 1 FROM cantieri_temporanei WHERE id=?", (ct_id,)
        ).fetchone():
            raise HTTPException(404, "Cantiere temporaneo non trovato")
        try:
            cur = con.execute(
                """INSERT INTO assegnazioni_cantiere
                   (cantiere_temp_id, dipendente_id, data_ingresso, note)
                   VALUES (?,?,?,?)""",
                (ct_id, body.dipendente_id, body.data_ingresso, body.note),
            )
        except Exception:
            raise HTTPException(409, "Dipendente già assegnato a questo cantiere")
    return {"id": cur.lastrowid, "cantiere_temp_id": ct_id, **body.model_dump()}


@router.delete("/{ct_id}/dipendenti/{dip_id}", status_code=204)
def rimuovi_dipendente(ct_id: int, dip_id: int):
    with db() as con:
        con.execute(
            "DELETE FROM assegnazioni_cantiere WHERE cantiere_temp_id=? AND dipendente_id=?",
            (ct_id, dip_id),
        )


# ── Corsi richiesti (a livello di cantiere — valgono per tutti) ───────────────

@router.put("/{ct_id}/corsi-richiesti")
def set_corsi_richiesti(ct_id: int, body: CorsiRichiesti):
    """
    Imposta la lista di corsi richiesti per TUTTI i dipendenti del cantiere.
    Sovrascrive corsi_richiesti su ogni riga di assegnazioni_cantiere.
    """
    ids_json = json.dumps(body.tipo_formazione_ids)
    with db() as con:
        con.execute(
            "UPDATE assegnazioni_cantiere SET corsi_richiesti=? WHERE cantiere_temp_id=?",
            (ids_json, ct_id),
        )
    return {"cantiere_temp_id": ct_id, "tipo_formazione_ids": body.tipo_formazione_ids}


@router.put("/{ct_id}/dipendenti/{dip_id}/corsi")
def set_corsi_dipendente(ct_id: int, dip_id: int, body: CorsiDipendente):
    """Sovrascrittura corsi per un singolo dipendente nel cantiere."""
    ids_json = json.dumps(body.tipo_formazione_ids)
    with db() as con:
        con.execute(
            """UPDATE assegnazioni_cantiere SET corsi_richiesti=?
               WHERE cantiere_temp_id=? AND dipendente_id=?""",
            (ids_json, ct_id, dip_id),
        )
    return {"cantiere_temp_id": ct_id, "dipendente_id": dip_id,
            "tipo_formazione_ids": body.tipo_formazione_ids}


# ── CHECKLIST — la view principale ───────────────────────────────────────────

@router.get("/{ct_id}/checklist")
def checklist(ct_id: int):
    """
    Restituisce la checklist completa: per ogni dipendente assegnato,
    per ogni corso richiesto, lo stato dell'attestato (se esiste).
    
    Struttura risposta:
    {
      "cantiere": {...},
      "corsi_richiesti": [...],   # lista tipi formazione
      "dipendenti": [
        {
          "dipendente": {...},
          "attestati": {
            tipo_formazione_id: {
              "stato": "valido"|"in_scadenza"|"scaduto"|"assente"|"nis"|"iaa"|...,
              "data_esecuzione": "...",
              "data_scadenza": "...",
              "giorni_alla_scadenza": 123
            }
          }
        }
      ]
    }
    """
    with db() as con:
        # cantiere
        ct = con.execute(
            "SELECT * FROM cantieri_temporanei WHERE id=?", (ct_id,)
        ).fetchone()
        if not ct:
            raise HTTPException(404, "Cantiere temporaneo non trovato")

        # assegnazioni
        assegnazioni = con.execute(
            """SELECT ac.dipendente_id, ac.corsi_richiesti,
                      ac.data_ingresso, ac.note,
                      d.cognome, d.nome, d.agenzia,
                      c.nome AS cantiere_sede
               FROM assegnazioni_cantiere ac
               JOIN dipendenti d ON d.id = ac.dipendente_id
               JOIN cantieri   c ON c.id = d.cantiere_id
               WHERE ac.cantiere_temp_id = ?
               ORDER BY d.cognome, d.nome""",
            (ct_id,),
        ).fetchall()

        if not assegnazioni:
            return {
                "cantiere": dict(ct),
                "corsi_richiesti": [],
                "dipendenti": [],
            }

        # ricava la union di tutti i corsi richiesti (da ogni assegnazione)
        all_corso_ids: set[int] = set()
        ass_map: dict[int, list[int]] = {}
        for a in assegnazioni:
            ids = json.loads(a["corsi_richiesti"] or "[]")
            ass_map[a["dipendente_id"]] = ids
            all_corso_ids.update(ids)

        # carica info tipi formazione richiesti
        corsi_info: dict[int, dict] = {}
        if all_corso_ids:
            placeholders = ",".join("?" * len(all_corso_ids))
            rows = con.execute(
                f"SELECT id, codice, nome, categoria, periodicita_anni "
                f"FROM tipi_formazione WHERE id IN ({placeholders})",
                list(all_corso_ids),
            ).fetchall()
            corsi_info = {r["id"]: dict(r) for r in rows}

        # carica tutti gli attestati pertinenti in un colpo solo
        dip_ids = [a["dipendente_id"] for a in assegnazioni]
        dip_ph = ",".join("?" * len(dip_ids))
        corso_ph = ",".join("?" * len(all_corso_ids)) if all_corso_ids else "NULL"
        attestati_rows = con.execute(
            f"""SELECT dipendente_id, tipo_formazione_id,
                       data_esecuzione, data_scadenza, stato,
                       CAST(julianday(data_scadenza) - julianday('now') AS INTEGER)
                           AS giorni_alla_scadenza
                FROM attestati
                WHERE dipendente_id IN ({dip_ph})
                  AND tipo_formazione_id IN ({corso_ph})
                ORDER BY data_esecuzione DESC""",
            dip_ids + list(all_corso_ids),
        ).fetchall() if all_corso_ids else []

        # indice: (dip_id, tipo_id) → attestato più recente
        att_index: dict[tuple, dict] = {}
        for r in attestati_rows:
            key = (r["dipendente_id"], r["tipo_formazione_id"])
            if key not in att_index:   # già ordinati per data DESC
                att_index[key] = dict(r)

    today = date.today().isoformat()

    result_dip = []
    for a in assegnazioni:
        dip_id = a["dipendente_id"]
        corsi_ids = ass_map[dip_id]
        att_per_corso: dict[int, dict] = {}
        for cid in corsi_ids:
            att = att_index.get((dip_id, cid))
            if att:
                att_per_corso[cid] = att
            else:
                # nessun attestato trovato
                att_per_corso[cid] = {
                    "stato": "assente",
                    "data_esecuzione": None,
                    "data_scadenza": None,
                    "giorni_alla_scadenza": None,
                }
        result_dip.append({
            "dipendente_id": dip_id,
            "cognome": a["cognome"],
            "nome": a["nome"],
            "agenzia": a["agenzia"],
            "cantiere_sede": a["cantiere_sede"],
            "data_ingresso": a["data_ingresso"],
            "note": a["note"],
            "corsi_richiesti": corsi_ids,
            "attestati": att_per_corso,
        })

    return {
        "cantiere": dict(ct),
        "corsi_richiesti": [corsi_info[i] for i in sorted(all_corso_ids) if i in corsi_info],
        "dipendenti": result_dip,
    }
