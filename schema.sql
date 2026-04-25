-- ============================================================
--  GESTIONE FORMAZIONI E VISITE MEDICHE
--  Schema SQLite  —  Fase 2
-- ============================================================
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. CANTIERI / SEDI
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cantieri (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    descrizione TEXT,
    attivo      INTEGER NOT NULL DEFAULT 1,   -- 1=sì, 0=no
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 2. DIPENDENTI
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dipendenti (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cantiere_id     INTEGER NOT NULL REFERENCES cantieri(id) ON DELETE RESTRICT,
    cognome         TEXT    NOT NULL,
    nome            TEXT    NOT NULL,
    agenzia         TEXT,                      -- es. "We Workeur", "Manpower"
    data_assunzione TEXT,                      -- formato ISO: YYYY-MM-DD
    attivo          INTEGER NOT NULL DEFAULT 1,
    note            TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dipendenti_cantiere ON dipendenti(cantiere_id);
CREATE INDEX IF NOT EXISTS idx_dipendenti_attivo   ON dipendenti(attivo);

-- ------------------------------------------------------------
-- 3. TIPI FORMAZIONE  (catalogo corsi — stabile nel tempo)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipi_formazione (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    codice                TEXT    NOT NULL UNIQUE,   -- es. "FORM_ART37"
    nome                  TEXT    NOT NULL,
    riferimento_normativo TEXT,                      -- es. "Art.37 D.Lgs 81/08"
    durata_ore            INTEGER,                   -- 4, 8, 12, 16, 20 …
    periodicita_anni      INTEGER,                   -- NULL = nessuna scadenza
    categoria             TEXT    NOT NULL DEFAULT 'formazione',
    -- categoria IN ('formazione','dpi','attrezzatura','antincendio',
    --               'pronto_soccorso','gas','elettrico','quota','visita','altro')
    attivo                INTEGER NOT NULL DEFAULT 1,
    note                  TEXT
);

-- ------------------------------------------------------------
-- 4. ATTESTATI  (una riga per ogni corso sostenuto da un dipendente)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attestati (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dipendente_id       INTEGER NOT NULL REFERENCES dipendenti(id)      ON DELETE CASCADE,
    tipo_formazione_id  INTEGER NOT NULL REFERENCES tipi_formazione(id) ON DELETE RESTRICT,
    data_esecuzione     TEXT    NOT NULL,   -- YYYY-MM-DD
    data_scadenza       TEXT,              -- calcolata: data_esec + periodicita_anni
    stato               TEXT    NOT NULL DEFAULT 'valido',
    -- stato IN ('valido','in_scadenza','scaduto','nis','iaa','iac','nd')
    ente_formatore      TEXT,
    note                TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attestati_dipendente      ON attestati(dipendente_id);
CREATE INDEX IF NOT EXISTS idx_attestati_tipo            ON attestati(tipo_formazione_id);
CREATE INDEX IF NOT EXISTS idx_attestati_data_scadenza   ON attestati(data_scadenza);
CREATE INDEX IF NOT EXISTS idx_attestati_stato           ON attestati(stato);

-- ------------------------------------------------------------
-- 5. VISITE MEDICHE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visite_mediche (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dipendente_id   INTEGER NOT NULL REFERENCES dipendenti(id) ON DELETE CASCADE,
    data_visita     TEXT    NOT NULL,   -- YYYY-MM-DD
    data_scadenza   TEXT,              -- YYYY-MM-DD  (calcolata: data_visita + durata_mesi)
    tipo            TEXT    NOT NULL DEFAULT 'annuale',
    -- tipo IN ('annuale','semestrale','trimestrale','quinquennale',
    --          'biennale','straordinaria','personalizzata')
    durata_mesi     INTEGER,           -- durata effettiva in mesi (sovrascrive il default del tipo)
    -- Esempi: annuale=12, semestrale=6, trimestrale=3
    -- prescrizione speciale → qualsiasi valore tra 1 e 120
    esito           TEXT    NOT NULL DEFAULT 'idoneo',
    -- esito IN ('idoneo','idoneo_limitazioni','non_idoneo','in_attesa')
    medico          TEXT,
    note            TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_visite_dipendente    ON visite_mediche(dipendente_id);
CREATE INDEX IF NOT EXISTS idx_visite_scadenza      ON visite_mediche(data_scadenza);
CREATE INDEX IF NOT EXISTS idx_visite_tipo          ON visite_mediche(tipo);

-- ============================================================
--  SEED: CATALOGO TIPI FORMAZIONE
--  (periodicita_anni NULL = nessuna scadenza normativa definita)
-- ============================================================
INSERT OR IGNORE INTO tipi_formazione
    (codice, nome, riferimento_normativo, durata_ore, periodicita_anni, categoria)
VALUES
-- Formazione generale / specifica
('FORM_ART37',      'Formazione Spec. Art.37',               'Art.37 D.Lgs 81/08',              12,  5, 'formazione'),
-- DPI III categoria
('DPI_ANTICAD',     'DPI III° Cat. Anticaduta',              'Art.77 D.Lgs 81/08',               8,  5, 'dpi'),
('DPI_AUTOPROT',    'DPI III° Cat. Autoprotezione',          'Art.77 D.Lgs 81/08',               8,  5, 'dpi'),
('FIT_TEST',        'Fit Test',                              'Art.77 D.Lgs 81/08',            NULL,  3, 'dpi'),
-- Preposto
('PREPOSTO',        'Preposto Art.19',                       'Art.19 D.Lgs 81/08',              12,  2, 'formazione'),
-- Attrezzature di lavoro (Art.73)
('MULETTI',         'Carrello Elevatore / Muletti',          'Art.73 D.Lgs 81/08',              12,  5, 'attrezzatura'),
('CARR_TELES',      'Carrello Semov. Braccio Teles.',        'Art.73 D.Lgs 81/08',              12,  5, 'attrezzatura'),
('CARR_TELES_ROT',  'Carrello Semov. Teles. Rotativo',       'Art.73 D.Lgs 81/08',              12,  5, 'attrezzatura'),
('CARR_IND_SEM',    'Carrello Ind./Sem./Teles./Rot. 16h',    'Art.73 D.Lgs 81/08',              16,  5, 'attrezzatura'),
('GRU_AUTOCARRO',   'Gru su Autocarro',                      'Art.73 D.Lgs 81/08',              12,  5, 'attrezzatura'),
('CTRL_SOLLEV',     'Controllo Accessori Sollevamento',      'Artt.36-37-169 D.Lgs 81/08',   NULL, NULL,'attrezzatura'),
('GRU_MOB_TRALIC',  'Gru Mobile Tralicciata',                'Art.73 D.Lgs 81/08',              14,  5, 'attrezzatura'),
('GRU_MOB_FALC',    'Gru Mobile Falcone Telesc.',            'Art.73 D.Lgs 81/08',              22,  5, 'attrezzatura'),
('PLE_CON_SENZA',   'PLE con/senza Stabilizzatori',          'Art.73 D.Lgs 81/08',              10,  5, 'attrezzatura'),
('PLE_SENZA',       'PLE senza Stabilizzatori',              'Art.73 D.Lgs 81/08',               8,  5, 'attrezzatura'),
('GRU_PONTE',       'Gru a Ponte / Bandiera',                'Art.73 D.Lgs 81/08',               8,  5, 'attrezzatura'),
('IMBRACATURA',     'Imbracatura Artt.71-73',                'Artt.71-73 D.Lgs 81/08',           8,  5, 'attrezzatura'),
('SEGNALATORE',     'Segnalatore Art.71-73',                 'Artt.71-73 D.Lgs 81/08',           8,  5, 'attrezzatura'),
('VERIF_FUNI',      'Verificatore Funi e Catene',            'Art.71-73 D.Lgs 81/08',           16,  5, 'attrezzatura'),
('CANNELLO',        'Cannello Ossigas Taglio/Riscaldo',       NULL,                            NULL, NULL,'attrezzatura'),
-- Spazi confinati
('SPAZI_CONF',      'Spazi Confinati Art.66',                'Art.66 DPR 177/11',               16,  5, 'formazione'),
-- Antincendio / Primo soccorso
('ANTINCENDIO',     'Antincendio DM 10/03/98',               'DM 10/03/98',                      8,  3, 'antincendio'),
('PRIMO_SOCC',      'Primo Soccorso DM 388/2003',            'DM 388/2003',                     12,  3, 'pronto_soccorso'),
-- Gas / Sostanze
('H2S',             'H2S Art.227',                           'Art.227 D.Lgs 81/08',              8,  3, 'gas'),
('SO2',             'SO2 Art.227',                           'Art.227 D.Lgs 81/08',              8,  3, 'gas'),
('SEVESO',          'SEVESO 105/15',                         'D.Lgs 105/15',                     8,  3, 'gas'),
('DIISOCIANATI',    'Diisocianati (REACH)',                  'All.XVII Reg.REACH',            NULL, NULL,'gas'),
-- Elettrico / ATEX
('PES_PAV_PEI',     'PES/PAV/PEI CEI 11-27',               'CEI 11-27',                       16,  5, 'elettrico'),
('ATEX',            'ATEX DPR 126/98',                       'DPR 126/98 Dir.94/9/CE',           8,  5, 'elettrico'),
('PED',             'PED - Direttiva 97/23',                 'Dir.97/23/CE',                  NULL, NULL,'elettrico'),
-- Protezione vie respiratorie
('OTOPROTETTORE',   'Otoprotettore Art.77',                  'Art.77 D.Lgs 81/08',            NULL,  5, 'dpi'),
('APVR',            'APVR Autorespiratore',                  'D.Lgs 81/08',                     20,  1, 'dpi'),
-- Lavori in quota / RLS / PIC
('LAVORI_QUOTA',    'Lavori in Quota',                       'Art.73 D.Lgs 81/08',            NULL,  5, 'quota'),
('RLS',             'RLS',                                   'Art.37 D.Lgs 81/08',              32,  1, 'formazione'),
('PIC',             'PIC (Person in Charge)',                NULL,                            NULL,  2, 'formazione'),
-- Visite mediche (gestite anche in tabella dedicata, ma catalogate qui)
('VISITA_ANN',      'Visita Medica Annuale',                 'Art.41 D.Lgs 81/08',            NULL,  1, 'visita'),
('VISITA_QQ',       'Visita Medica Quinquennale',            'Art.41 D.Lgs 81/08',            NULL,  5, 'visita');


-- ============================================================
--  SEED: CANTIERI dall'Excel originale
-- ============================================================
INSERT OR IGNORE INTO cantieri (nome) VALUES
    ('Massafra'),
    ('Eni Versalis - Ragusa'),
    ('ISAB - Priolo'),
    ('Enel - Cerano'),
    ('Co.Va. - Viggiano'),
    ('Eni Versalis - Crescentino'),
    ('Solvay - Spinetta M.go'),
    ('Ferrara'),
    ('We Workeur'),
    ('OpenJobs'),
    ('Manpower'),
    ('Etjca');


-- ============================================================
--  VISTE UTILI  (query pre-costruite per la web app)
-- ============================================================

-- Vista: attestati con tutti i dettagli
CREATE VIEW IF NOT EXISTS v_attestati AS
SELECT
    a.id,
    d.cognome || ' ' || d.nome          AS dipendente,
    c.nome                              AS cantiere,
    d.agenzia,
    tf.codice                           AS codice_corso,
    tf.nome                             AS corso,
    tf.categoria,
    tf.periodicita_anni,
    a.data_esecuzione,
    a.data_scadenza,
    a.stato,
    a.ente_formatore,
    a.note,
    -- giorni alla scadenza (negativo = già scaduto)
    CASE
        WHEN a.data_scadenza IS NULL THEN NULL
        ELSE CAST(julianday(a.data_scadenza) - julianday('now') AS INTEGER)
    END AS giorni_alla_scadenza
FROM attestati a
JOIN dipendenti      d  ON d.id  = a.dipendente_id
JOIN cantieri        c  ON c.id  = d.cantiere_id
JOIN tipi_formazione tf ON tf.id = a.tipo_formazione_id;

-- Vista: scadenze imminenti (entro 90 giorni o già scadute)
CREATE VIEW IF NOT EXISTS v_scadenze_imminenti AS
SELECT *
FROM v_attestati
WHERE giorni_alla_scadenza IS NOT NULL
  AND giorni_alla_scadenza <= 90
ORDER BY giorni_alla_scadenza;

-- Vista: visite mediche con dettagli
CREATE VIEW IF NOT EXISTS v_visite AS
SELECT
    vm.id,
    d.cognome || ' ' || d.nome  AS dipendente,
    c.nome                      AS cantiere,
    d.agenzia,
    vm.tipo,
    vm.durata_mesi,
    vm.data_visita,
    vm.data_scadenza,
    vm.esito,
    vm.medico,
    vm.note,
    CASE
        WHEN vm.data_scadenza IS NULL THEN NULL
        ELSE CAST(julianday(vm.data_scadenza) - julianday('now') AS INTEGER)
    END AS giorni_alla_scadenza
FROM visite_mediche vm
JOIN dipendenti d ON d.id = vm.dipendente_id
JOIN cantieri   c ON c.id = d.cantiere_id;

-- Vista: riepilogo per cantiere
CREATE VIEW IF NOT EXISTS v_riepilogo_cantieri AS
SELECT
    c.nome                                              AS cantiere,
    COUNT(DISTINCT d.id)                                AS tot_dipendenti,
    COUNT(DISTINCT CASE WHEN d.attivo = 1 THEN d.id END) AS dip_attivi,
    SUM(CASE WHEN a.data_scadenza < date('now') THEN 1 ELSE 0 END)
                                                        AS attestati_scaduti,
    SUM(CASE WHEN a.data_scadenza BETWEEN date('now') AND date('now','+60 days') THEN 1 ELSE 0 END)
                                                        AS attestati_in_scadenza_60gg
FROM cantieri c
LEFT JOIN dipendenti      d ON d.cantiere_id = c.id
LEFT JOIN attestati       a ON a.dipendente_id = d.id
GROUP BY c.id, c.nome
ORDER BY c.nome;

-- ============================================================
--  CANTIERI TEMPORANEI  (aggiunta Fase 4b)
-- ============================================================

-- Tabella cantieri temporanei
CREATE TABLE IF NOT EXISTS cantieri_temporanei (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT    NOT NULL,          -- es. "Fermata Major Mantova"
    cliente      TEXT,                      -- es. "ENI Versalis"
    data_inizio  TEXT,                      -- YYYY-MM-DD
    data_fine    TEXT,                      -- YYYY-MM-DD (null = in corso)
    descrizione  TEXT,
    attivo       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Assegnazioni: dipendenti → cantiere temporaneo
-- corsi_richiesti = JSON array di tipo_formazione_id
-- es. [1, 3, 8, 12]  (IDs dal catalogo tipi_formazione)
CREATE TABLE IF NOT EXISTS assegnazioni_cantiere (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cantiere_temp_id    INTEGER NOT NULL REFERENCES cantieri_temporanei(id) ON DELETE CASCADE,
    dipendente_id       INTEGER NOT NULL REFERENCES dipendenti(id)          ON DELETE CASCADE,
    corsi_richiesti     TEXT    NOT NULL DEFAULT '[]',  -- JSON array di tipo_formazione_id
    data_ingresso       TEXT,
    note                TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(cantiere_temp_id, dipendente_id)  -- un dipendente una sola volta per cantiere
);

CREATE INDEX IF NOT EXISTS idx_ass_cantiere  ON assegnazioni_cantiere(cantiere_temp_id);
CREATE INDEX IF NOT EXISTS idx_ass_dip       ON assegnazioni_cantiere(dipendente_id);
