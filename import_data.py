"""
Fase 5 — Import dati Excel → SQLite
Legge il file originale e popola il database con:
  - dipendenti (186)
  - attestati formativi
  - visite mediche (colonne 37 e 38)

Uso:
  python import_data.py                         # usa percorso default
  python import_data.py /path/to/file.xlsx      # percorso custom
"""
import sys
import re
import pathlib
import sqlite3
import json
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

try:
    import pandas as pd
except ImportError:
    print("Installa pandas: pip install pandas openpyxl")
    sys.exit(1)

# ── Configurazione ────────────────────────────────────────────────────────────
EXCEL_PATH = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
             pathlib.Path(__file__).parent.parent / "File____FORMAZIONI.xlsx"
DB_PATH    = pathlib.Path(__file__).parent / "formazioni.db"
SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"

# Mappatura colonna Excel → tipo_formazione_id (dal catalogo seed)
# (col_idx, tipo_formazione_id)
COLS = [
    (3,  1),   # Form_Art37           → FORM_ART37
    (4,  2),   # DPI_Anticad          → DPI_ANTICAD
    (5,  3),   # DPI_Autoprot         → DPI_AUTOPROT
    (6,  4),   # FitTest              → FIT_TEST
    (7,  5),   # Preposto             → PREPOSTO
    (8,  6),   # Muletti              → MULETTI
    (9,  7),   # Carr_Teles           → CARR_TELES
    (10, 8),   # Carr_TelesRot        → CARR_TELES_ROT
    (11, 9),   # Carr_Ind_Sem         → CARR_IND_SEM
    (12, 10),  # Gru_Autocarro        → GRU_AUTOCARRO
    (13, 11),  # Ctrl_Sollevamento    → CTRL_SOLLEV
    (14, 12),  # Gru_Mobile_Tralic    → GRU_MOB_TRALIC
    (15, 13),  # Gru_Mobile_Falcone   → GRU_MOB_FALC
    (16, 14),  # PLE_ConSenza         → PLE_CON_SENZA
    (17, 15),  # PLE_Senza            → PLE_SENZA
    (18, 21),  # Spazi_Conf           → SPAZI_CONF
    (19, 22),  # Antincendio          → ANTINCENDIO
    (20, 23),  # Primo_Soccorso       → PRIMO_SOCC
    (21, 16),  # Gru_Ponte            → GRU_PONTE
    (22, 20),  # Cannello_Ossigas     → CANNELLO
    (23, 30),  # PED                  → PED
    (24, 24),  # H2S                  → H2S
    (25, 25),  # SO2                  → SO2
    (26, 26),  # SEVESO               → SEVESO
    (27, 28),  # PES_PAV_PEI          → PES_PAV_PEI
    (28, 29),  # ATEX                 → ATEX
    (29, 17),  # Imbracatura          → IMBRACATURA
    (30, 18),  # Segnalatore          → SEGNALATORE
    (31, 31),  # Otoprotettore        → OTOPROTETTORE
    (32, 32),  # APVR                 → APVR
    (33, 19),  # Verif_Funi           → VERIF_FUNI
    (34, 35),  # PIC                  → PIC
    (35, 33),  # Lavori_Quota         → LAVORI_QUOTA
    (36, 34),  # RLS                  → RLS
    (39, 27),  # Diisocianati         → DIISOCIANATI
]
VISITA_ANN_COL = 37   # colonna visita annuale
VISITA_QQ_COL  = 38   # colonna visita quinquennale

# Normalizzazione nomi cantieri (da Excel → DB)
CANTIERE_MAP = {
    'Co.Va. - Viggiano':         'Co.Va. - Viggiano',
    'Enel - Cerano':             'Enel - Cerano',
    'Eni Versalis - Ragusa':     'Eni Versalis - Ragusa',
    'Eni Versalis -Crescentino': 'Eni Versalis - Crescentino',
    'Etjca':                     'Etjca',
    'FERRARA':                   'Ferrara',
    'ISAB - Priolo':             'ISAB - Priolo',
    'Manpower':                  'Manpower',
    'Massafra':                  'Massafra',
    'OPenJobs':                  'OpenJobs',
    'Solvay - Spinetta M.go':    'Solvay - Spinetta M.go',
    'We Workeur':                'We Workeur',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_cell(val):
    """
    Returns (date_iso: str|None, stato_speciale: str|None)
    stato_speciale: 'nis','iaa','iac','nd' oppure None
    """
    if val is None or (isinstance(val, float) and __import__('math').isnan(val)):
        return None, None
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d'), None
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none'):
        return None, None
    s_up = s.upper()
    if s_up in ('NO', 'N', 'NP', 'L', 'NO ', 'ONO', 'NO\n'):
        return None, 'NO'
    if s_up == '??':
        return None, 'ND'
    # check special status tokens
    found_status = None
    for st in ('NIS', 'IAA', 'IAC'):
        if st in s_up:
            found_status = st.lower()
            break
    # try to extract date
    m = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = '20' + y
        try:
            dt = datetime(int(y), int(mo), int(d))
            return dt.strftime('%Y-%m-%d'), found_status
        except Exception:
            pass
    if found_status:
        return None, found_status
    return None, None


def calc_scadenza(data_exec: str, periodicita_anni: int | None) -> str | None:
    if not periodicita_anni or not data_exec:
        return None
    try:
        dt = date.fromisoformat(data_exec)
        return (dt + relativedelta(years=periodicita_anni)).isoformat()
    except ValueError:
        return None


def calc_scadenza_mesi(data_visita: str, mesi: int | None) -> str | None:
    if not mesi or not data_visita:
        return None
    try:
        dt = date.fromisoformat(data_visita)
        return (dt + relativedelta(months=mesi)).isoformat()
    except ValueError:
        return None


def calc_stato(data_scadenza: str | None) -> str:
    if not data_scadenza:
        return 'valido'
    try:
        exp = date.fromisoformat(data_scadenza)
        diff = (exp - date.today()).days
        if diff < 0:
            return 'scaduto'
        if diff <= 60:
            return 'in_scadenza'
        return 'valido'
    except ValueError:
        return 'valido'


# ── Main import ───────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print("  IMPORT DATI EXCEL → DATABASE")
    print(f"{'='*55}")
    print(f"  Excel : {EXCEL_PATH}")
    print(f"  DB    : {DB_PATH}")
    print()

    if not EXCEL_PATH.exists():
        print(f"ERRORE: file Excel non trovato: {EXCEL_PATH}")
        sys.exit(1)

    # Init DB se non esiste
    if not DB_PATH.exists():
        print("Database non trovato, inizializzazione schema...")
        con = sqlite3.connect(DB_PATH)
        con.executescript(SCHEMA_PATH.read_text())
        con.commit()
        con.close()
        print("Schema creato.")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    # ── Carica lookup tables ──────────────────────────────────────────────────
    cantieri_db = {r['nome']: r['id'] for r in con.execute("SELECT id, nome FROM cantieri")}
    tf_db       = {r['id']: r for r in con.execute("SELECT * FROM tipi_formazione")}

    print(f"Cantieri nel DB: {len(cantieri_db)}")
    print(f"Tipi formazione nel DB: {len(tf_db)}")
    print()

    # ── Leggi Excel ───────────────────────────────────────────────────────────
    print("Lettura file Excel...")
    df_raw = pd.read_excel(str(EXCEL_PATH), sheet_name='Elenco Lav.', header=None)
    print(f"Righe lette: {len(df_raw)}")

    # ── Parse righe ──────────────────────────────────────────────────────────
    stats = {
        'dipendenti_inseriti': 0,
        'dipendenti_saltati': 0,
        'attestati_inseriti': 0,
        'attestati_saltati_no': 0,
        'attestati_speciali': 0,
        'visite_inserite': 0,
        'cantieri_mancanti': set(),
    }

    for i in range(11, len(df_raw)):
        row = df_raw.iloc[i].tolist()

        # ── Identifica riga ──────────────────────────────────────────────────
        cantiere_raw = str(row[0]).strip() if pd.notna(row[0]) else ''
        nome_raw  = str(row[1]).strip() if pd.notna(row[1]) else ''
        nome_col2 = str(row[2]).strip() if pd.notna(row[2]) else ''
        nome_full = nome_raw if (nome_raw and nome_raw.lower() not in ('nan','')) else nome_col2

        if not nome_full or nome_full.lower() in ('nan','') or \
           not cantiere_raw or cantiere_raw.lower() in ('nan',''):
            continue

        # ── Normalizza cantiere ──────────────────────────────────────────────
        cantiere_nome = CANTIERE_MAP.get(cantiere_raw)
        if not cantiere_nome:
            stats['cantieri_mancanti'].add(cantiere_raw)
            stats['dipendenti_saltati'] += 1
            continue

        cantiere_id = cantieri_db.get(cantiere_nome)
        if not cantiere_id:
            # Crea cantiere al volo
            cur = con.execute("INSERT INTO cantieri (nome) VALUES (?)", (cantiere_nome,))
            con.commit()
            cantiere_id = cur.lastrowid
            cantieri_db[cantiere_nome] = cantiere_id
            print(f"  [!] Cantiere creato: {cantiere_nome}")

        # ── Split cognome/nome ────────────────────────────────────────────────
        parts = nome_full.split()
        cognome = parts[0].upper() if parts else nome_full.upper()
        nome_p  = ' '.join(parts[1:]).upper() if len(parts) > 1 else ''

        # ── Agenzia: cantieri interinali ──────────────────────────────────────
        agenzie = {'We Workeur','OpenJobs','Manpower','Etjca'}
        agenzia = cantiere_nome if cantiere_nome in agenzie else None

        # ── Inserisci dipendente (skip se già esiste con stesso nome+cantiere) ─
        existing = con.execute(
            "SELECT id FROM dipendenti WHERE cognome=? AND nome=? AND cantiere_id=?",
            (cognome, nome_p, cantiere_id)
        ).fetchone()

        if existing:
            dip_id = existing['id']
            stats['dipendenti_saltati'] += 1
        else:
            cur = con.execute(
                """INSERT INTO dipendenti (cantiere_id, cognome, nome, agenzia, attivo)
                   VALUES (?,?,?,?,1)""",
                (cantiere_id, cognome, nome_p, agenzia)
            )
            dip_id = cur.lastrowid
            stats['dipendenti_inseriti'] += 1

        # ── Attestati formativi ───────────────────────────────────────────────
        for col_idx, tf_id in COLS:
            val = row[col_idx] if col_idx < len(row) else None
            data_exec, stato_spec = parse_cell(val)

            # Skip celle NO / vuote
            if stato_spec == 'NO' or (data_exec is None and stato_spec is None):
                stats['attestati_saltati_no'] += 1
                continue

            tf = tf_db.get(tf_id)
            periodicita = tf['periodicita_anni'] if tf else None

            if stato_spec in ('nis', 'iaa', 'iac', 'nd') or                (data_exec is None and stato_spec not in (None, 'NO')):
                # Stato speciale: se non c'è data esecuzione, salta
                if data_exec is None:
                    stats['attestati_saltati_no'] += 1
                    continue
                scadenza = None
                stato    = stato_spec or 'nd'
                stats['attestati_speciali'] += 1
            else:
                scadenza = calc_scadenza(data_exec, periodicita)
                stato    = calc_stato(scadenza)

            # Evita duplicati (stesso dip + stesso corso)
            dup = con.execute(
                "SELECT id FROM attestati WHERE dipendente_id=? AND tipo_formazione_id=?",
                (dip_id, tf_id)
            ).fetchone()
            if dup:
                # Aggiorna con data più recente
                con.execute(
                    """UPDATE attestati SET data_esecuzione=?, data_scadenza=?,
                       stato=?, updated_at=datetime('now') WHERE id=?""",
                    (data_exec, scadenza, stato, dup['id'])
                )
            else:
                con.execute(
                    """INSERT INTO attestati
                       (dipendente_id, tipo_formazione_id, data_esecuzione,
                        data_scadenza, stato)
                       VALUES (?,?,?,?,?)""",
                    (dip_id, tf_id, data_exec, scadenza, stato)
                )
            stats['attestati_inseriti'] += 1

        # ── Visite mediche ────────────────────────────────────────────────────
        for col_idx, tipo, durata_mesi in [
            (VISITA_ANN_COL, 'annuale',      12),
            (VISITA_QQ_COL,  'quinquennale', 60),
        ]:
            val = row[col_idx] if col_idx < len(row) else None
            data_vis, stato_spec = parse_cell(val)
            if stato_spec == 'NO' or (data_vis is None and stato_spec is None):
                continue

            # Se non c'è data visita (solo stato speciale), salta
            if data_vis is None:
                continue
            scadenza = calc_scadenza_mesi(data_vis, durata_mesi)
            esito    = 'non_idoneo' if stato_spec == 'nis' else \
                       'in_attesa'  if stato_spec in ('iaa','iac') else 'idoneo'

            dup = con.execute(
                "SELECT id FROM visite_mediche WHERE dipendente_id=? AND tipo=?",
                (dip_id, tipo)
            ).fetchone()
            if dup:
                con.execute(
                    """UPDATE visite_mediche SET data_visita=?, data_scadenza=?,
                       durata_mesi=?, esito=?, updated_at=datetime('now') WHERE id=?""",
                    (data_vis, scadenza, durata_mesi, esito, dup['id'])
                )
            else:
                con.execute(
                    """INSERT INTO visite_mediche
                       (dipendente_id, data_visita, data_scadenza, tipo, durata_mesi, esito)
                       VALUES (?,?,?,?,?,?)""",
                    (dip_id, data_vis, scadenza, tipo, durata_mesi, esito)
                )
            stats['visite_inserite'] += 1

    con.commit()

    # ── Riepilogo finale ──────────────────────────────────────────────────────
    tot_dip  = con.execute("SELECT COUNT(*) FROM dipendenti").fetchone()[0]
    tot_att  = con.execute("SELECT COUNT(*) FROM attestati").fetchone()[0]
    tot_vis  = con.execute("SELECT COUNT(*) FROM visite_mediche").fetchone()[0]
    scaduti  = con.execute("SELECT COUNT(*) FROM attestati WHERE stato='scaduto'").fetchone()[0]
    in_scad  = con.execute("SELECT COUNT(*) FROM attestati WHERE stato='in_scadenza'").fetchone()[0]
    validi   = con.execute("SELECT COUNT(*) FROM attestati WHERE stato='valido'").fetchone()[0]
    speciali = con.execute("SELECT COUNT(*) FROM attestati WHERE stato IN ('nis','iaa','iac','nd')").fetchone()[0]

    print(f"\n{'─'*55}")
    print("  RISULTATI IMPORT")
    print(f"{'─'*55}")
    print(f"  Dipendenti inseriti  : {stats['dipendenti_inseriti']}")
    print(f"  Dipendenti aggiornati: {stats['dipendenti_saltati']}")
    print(f"  Attestati importati  : {stats['attestati_inseriti']}")
    print(f"    → Validi           : {validi}")
    print(f"    → In scadenza      : {in_scad}")
    print(f"    → Scaduti          : {scaduti}")
    print(f"    → Speciali (NIS/IAA/IAC): {speciali}")
    print(f"  Visite mediche       : {stats['visite_inserite']}")
    print(f"{'─'*55}")
    print(f"  TOTALE NEL DB:")
    print(f"    Dipendenti  : {tot_dip}")
    print(f"    Attestati   : {tot_att}")
    print(f"    Visite      : {tot_vis}")
    if stats['cantieri_mancanti']:
        print(f"\n  [!] Cantieri non mappati: {stats['cantieri_mancanti']}")
    print(f"\n  Import completato.")
    print(f"{'='*55}\n")

    con.close()


if __name__ == '__main__':
    main()
