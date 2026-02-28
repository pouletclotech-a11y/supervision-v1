# Ingestion Specifications

## 1. Source of Truth vs. Proof

The system handles two main file types, which serve distinct purposes:

-   **`.xls` / `.xlsx` (Excel)**: The **Source of Truth**. This file contains the structured data.
-   **`.pdf` (PDF)**: The **Proof of Context** and secondary extraction source.

### 1.1 Pairing & Integrity Logic (Phase 6.2)
-   The system attempts to pair files based on their filename or `source_message_id`.
-   **Integrity Check**: Lorsque l'XLS et le PDF sont présents, un `match_pct` est calculé via la signature `(site_code, time, alarm_code)`. Résultats stockés dans `import_metadata["integrity_check"]`.
-   **Déduplication Spécifique (Phase C Roadmap 9)** : Les doublons exacts identifiés a posteriori sont marqués via la colonne `dup_count = 1`. Une vue `view_events_deduplicated` est disponible pour les outils de reporting.

## 2. Extraction & Normalization

### 2.1 Key Fields Extracted
| Field | Source | Cleaning Rule | Purpose |
| :--- | :--- | :--- | :--- |
| **`site_code`** | XLS Col A / PDF | **Normalized** | Grouping events. |
| **`alarm_code`** | XLS Col E / PDF | Strict strip, preserves suffixes (ex: `-MHS`) | Precise identification. |
| **`state`** | XLS/PDF | Mapping: APPARITION, DISPARITION, etc. | Incident lifecycle. |

### 2.2 Cleaning Rules
- **Excel**: Systematic `strip()`, removal of wrappers `="..."`, normalization of internal spaces.
- **Site Code Normalization**:
    1. Strip wrappers `="..."`.
    2. Trim spaces.
    3. Si numérique uniquement : `lstrip('0')`. Si résultat vide -> `"0"`.
    4. **Préfixe "C-" (Phase B Roadmap 9)** : Si le code correspond au pattern `^C-[0-9]+$`, le préfixe `C-` est retiré pour harmonisation (ex: `C-69000` -> `69000`).
    5. Les codes alphanumériques complexes restent inchangés.

## 3. Filtering & Suppression
-   **Format Filter**: Explicit acceptance list per provider (e.g., `["pdf", "xls", "xlsx"]`). Unlisted formats like `.png` are rejected with status `IGNORED`.
-   **Operator Actions**: Events identified as actions operator (e.g., via `$HRAUDIT` or specific PDF patterns) are stored but excluded from Alerts and Incident Reconstruction.

## 4. Parsers

### Excel Parser (`excel_parser.py`)
-   Handles both legacy TSV-like `.xls` and binary `.xlsx`.
-   Strict cell cleaning and state mapping.

### PDF Parser (`pdf_parser.py`)
-   Enriched extraction: captures Day, Date, Time, Full Alarm Code and State.
-   Detects `OPERATOR_ACTION`.

## 5. Business Rules Evaluation (V1)
After persistence, each event batch is processed by the `BusinessRuleEngine`:
- **Keywords/Codes**: Based on `config.yml` patterns.
- **Persistence**: Hits are stored in `event_rule_hits` with an explanation and site context.
- **Performance**: Evaluation is optimized to be < 1ms per event, non-blocking for the ingestion flow.
