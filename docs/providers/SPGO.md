# Provider Specification — SPGO (XLS/TSV)

## Format de fichier
- Extension : `.xls` (mais format réel TSV - Tab Separated Values).
- Encodage : `latin-1`.

## Structure des colonnes (Indices 0..5)
| Index | Colonne | Description |
| :--- | :--- | :--- |
| 0 | Col A | **Code Site** (`C-xxxxx` ou numérique 5-8 chars). |
| 1 | Col B | **Jour** (Lun, Mar...) ou **Nom Client** (si entête de bloc). |
| 2 | Col C | **Date/Heure** (`dd/mm/yyyy HH:MM:SS`) ou **Heure seule** (`HH:MM:SS`). |
| 3 | Col D | **Action métier** (APPARITION...) ou **Message** (si note opérateur). |
| 4 | Col E | **Code Alarme** (Conservé tel quel). |
| 5 | Col F | **Détails/Message**. |

## Règles de Parsing

### 1. Détection de Bloc
- Une valeur en Col A démarre un nouveau bloc.
- Si Col B est rempli mais Col C/D sont vides, Col B = `client_name`.

### 2. Événements de Sécurité
- Détecté si Col B contient un jour et Col C contient une date complète.
- `normalized_type` mappé sur Col D.
- `status` = `CRITICAL` si Col D == "APPARITION", sinon `INFO`.

### 3. Notes Opérateur (OPERATOR_NOTE)
- Détecté si **Col B est vide** ET **Col C contient une heure seule**.
- **Horodatage** : Reconstruit en utilisant la date du dernier événement de sécurité complet rencontré dans le bloc.
- `normalized_type` = `OPERATOR_NOTE`.
- `raw_message` = fusion de Col D et Col F.

### 4. Codes d'alarme
- Extraits de Col E en priorité sans normalisation.
- Fallback sur `$XXXX` ou 4 chiffres dans le message si Col E est vide.

## PDF Companion
- Le PDF suit le même format visuel et doit être parsé en "miroir" pour valider l'ingestion XLS.
