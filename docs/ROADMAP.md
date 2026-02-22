# Project Roadmap

This document outlines the current status (V1), immediate priorities (B1), and the long-term vision (V2) for the Supervision Tool.

> [!NOTE]
> **Priority Rule**: No V2 feature implementation should begin before the **B1 (Alarm Rules)** phase is fully validated operationally.

---

## V1: Foundation (Stable & Acquired)
**Status**: `RELEASED` | **Version**: `1.0`

The foundation of the system is now stable and operational.

- **Ingestion**: 
  - Robust parsing of `.xls` (Source of Truth) and `.pdf` (Proof).
  - Normalization of events (Type, Severity, Zone, Site, Client).
  - "Dropbox" style ingress (`dropbox_in`) with automated archival.
- **Data Integrity**:
  - **Anti-Deduplication**: Two-tier logic (Burst Collapse + Hash-based Anti-Spam).
  - **Persistence**: PostgreSQL 16 + TimescaleDB for time-series efficiency.
- **User Interface**:
  - **Data Validation**: Dark theme, Zebra striping (Site Code based), effective filtering.
  - **Layout**: Stable responsive navigation.

---

## B2: Advanced Engine (XLS V2 + Alerting V3)
**Status**: `STARTING`

Evolution of the ingestion and alerting system to support complex business logic.

### 1. XLS Parsing V2 (Context-Aware)
- **Cell-Aware Reading**: Handle merged cells and inheritance from previous rows/columns.
- **Propagation Logic**: 
  - `site_code` (Col A) propagation to empty rows.
  - `day` (Col B) propagation to empty rows.
  - `date` (Col C) inheritance when only time is provided.
- **Full Timestamps**: Reconstruct complete UTC timestamps for every event line.

### 2. Incident Management
- **Pairing**: Match `APPARITION` and `DISPARITION` events to create `Incidents`.
- **States**: `OPEN`, `CLOSED`, `OPEN_ONLY` (no disparition).
- **Analytics**: Calculate incident duration and groupings.

### 3. Advanced Rules Engine
- **Event Catalog**: Centralized registry of event codes, categories, and default severities.
- **Frequency Analysis**: $X$ occurrences over $Y$ days (sliding window).
- **Temporal Sequences**: Detect Pattern A followed by Pattern B within $\Delta t$.
- **Boolean Logic**: Tree-based `AND` / `OR` rules using a library of named conditions.

### 4. Interactive Dry Run
- **Explanations**: Detailed "Why it matched" or "Why it failed" reports.
- **Visual Builder**: Rule construction interface integrated with the test engine.

---

## V2: Evolution & Business Logic (Vision)

**Status**: `PLANNED`

Scaling the tool for multi-user, multi-site operational excellence.

### 1. User Management & Security
- **RBAC**: Admin, Operator, Read-Only roles.
- **Access Control**: Granular permissions for Settings, Rules, and Dashboard access.

### 2. Advanced Dashboards
- **Synthetic Views**: High-level alert summaries.
- **Incident View**: Focused view on active problems.
- **Site/Group Views**: Aggregated statistics by site or custom groups.

### 3. Ticketing & Workflows
- **Lifecycle**: New -> In Progress -> Closed.
- **Actions**:
  - Emails (Internal/Client).
  - Technician Intervention requests.
- **Traceability**: Full history of actions and comments.

### 4. Intelligent Grouping
- **Concept**: Transform raw "Events" into qualified "Alerts" and "Incidents".
- **Goal**: Reduce noise by hiding raw lines unless specifically requested.

### 5. Client Groups
- **Logic**: Regroup sites by Client Chain or Region (fuzzy matching or manual grouping).
- **Analytics**: Multi-day trends per group.

### 6. Complex Rules Engine
- **Composite Rules**: `(Rule A AND Rule B) OR Rule C`.
- **Dependencies**: Prioritization of alarms based on context.
- **Calendars (FR)**:
  - Fixed Public Holidays.
  - Variable Holidays.
  - Integration as conditional logic for rules.

### 7. Internationalization (i18n)
- **Toggle**: FR / EN.
- **Default**: French.
