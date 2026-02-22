# Ingestion Specifications

## 1. Source of Truth vs. Proof

The system handles two main file types, which serve distinct purposes:

-   **`.xls` (Excel/HTML/XML)**: The **Source of Truth**. This file contains the structured data that is parsed, normalized, and stored as events.
-   **`.pdf` (PDF)**: The **Proof of Context**. This file is archived alongside the XLS as an immutable reference for human verification but is *not* the primary source for structured data in V1.

### 1.1 Pairing Logic
-   The system attempts to pair files based on their filename (e.g., `Report_A.xls` pairs with `Report_A.pdf`).
-   When inspecting an event in the UI, the system retrieves the sibling PDF to allow side-by-side verification.

## 2. Extraction & Normalization

The normalization process transforms raw log messages into structured business events.

### 2.1 Key Fields Extracted
| Field | Source | Cleaning Rule | Purpose |
| :--- | :--- | :--- | :--- |
| **`site_code`** | XLS Column A | **Digits Only** (Regex `\D` removal) | Grouping events by physical location. |
| **`client_name`** | XLS Column B | Trim whitespace | Human-readable identification. |
| **`weekday_label`** | Derived/XLS | Preserved as is (e.g., "Lun", "Mar") | Context for future calendar rules. |
| **`raw_message`** | XLS Content | Trim whitespace | The basis for normalization regexes. |

### 2.2 Normalization Rules (Config)
Rules are defined in `backend/config.yml`.
-   **Pattern**: Regex matching the `raw_message`.
-   **Output**: `event_type`, `severity` (CRITICAL, WARNING, INFO, SUCCESS).
-   **Extraction**: Capturing groups map to metadata (e.g., Zone Label).

## 3. Deduplication (Anti-Spam)

### Level 1: Burst Collapse (Business Logic)
-   **Goal**: Aggregate related events into one "Burst".
-   **Key**: `site_code + normalized_type + zone_label + TIME_BUCKET`
-   **Time Bucket**: `timestamp / 5s` (Configurable).
-   **Behavior**: Only the *first* event of a burst bucket is stored.

### Level 2: Anti-Spam (Safety Net)
-   **Goal**: Prevent strict duplicates from infinite retry loops or re-imports.
-   **Key**: SHA256 of `site_code + raw_message + exact_timestamp`.
-   **Logic**: If the hash exists in the Anti-Spam cache (Redis), the event is dropped immediately.

## 4. Normalisation & Enrichissement
-   **Text Normalizer**: Nettoyage des messages (suppression des codes techniques redondants, espaces multiples) pour faciliter le matching de keywords.
-   **Tagging**: Lookup dans le catalogue pour assigner `category` et `impact`.
-   **Normalized Message**: Version simplifiée générée pour l'évaluation des règles d'alerte.

## 5. Pairing d'Incidents (Signature-based)
-   **Algorithme**: Chaque événement génère une signature (Hash de `site_code` + `type`).
-   **Pairing**: Si un événement de type `DISPARITION` match une signature `APPARITION` active, ils sont liés au même `incident_id`.
-   **États**: Un incident est marqué `CLOSED` dès qu'un pairing est validé. Sinon, il reste `OPEN`.

## 4. Parsers

### Excel Parser (`excel_parser.py`)
-   **Type**: Custom parser for "Fake Excel" (HTML tables disguised as .xls).
-   **Logic**:
    1.  Detects "Site Header" rows (Context).
    2.  Parses "Event Rows" below headers.
    3.  Extracts `Date`, `Time`, `Message`, `State` (Apparition/Disparition).

### PDF Parser (`pdf_parser.py`)
-   **Library**: `pdfplumber`.
-   **Usage**: Extracts text for indexing/archival. Used heavily for debugging if XLS fails.
