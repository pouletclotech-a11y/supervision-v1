# Ingestion Specifications

## 1. Source of Truth vs. Proof

The system handles two main file types, which serve distinct purposes:

-   **`.xls` / `.xlsx` (Excel)**: The **Source of Truth**. This file contains the structured data.
-   **`.pdf` (PDF)**: The **Proof of Context** and secondary extraction source.

### 1.1 Pairing & Integrity Logic (Phase 6.2)
-   The system attempts to pair files based on their filename or `source_message_id`.
-   **Integrity Check**: When both XLS and PDF are present, a `match_pct` is computed using the signature `(site_code, timestamp, alarm_code)`. Results are stored in `import_metadata["integrity_check"]`.

## 2. Extraction & Normalization

### 2.1 Key Fields Extracted
| Field | Source | Cleaning Rule | Purpose |
| :--- | :--- | :--- | :--- |
| **`site_code`** | XLS Col A / PDF | **Digits Only** | Grouping events. |
| **`alarm_code`** | XLS Col E / PDF | Strict strip, preserves suffixes (ex: `-MHS`) | Precise identification. |
| **`state`** | XLS/PDF | Mapping: APPARITION, DISPARITION, etc. | Incident lifecycle. |

### 2.2 Cleaning Rules
-   **Excel**: Systematic `strip()`, removal of wrappers `="..."`, normalization of internal spaces.

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
