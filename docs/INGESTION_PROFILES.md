# Spécification : Ingestion Profiles (V3.1)

Les **Ingestion Profiles** permettent de charger des formats de fichiers hétérogènes (XLS, PDF, CSV) de manière purement déclarative. 

---

## 1. Format du Profil (YAML)

### En-tête et Priorité
```yaml
version: "1.1"
profile_id: "vms_partner_standard"
priority: 100  # Utilisé en cas d'ambiguïté (plus haut = gagne)
description: "Format standard d'export du partenaire VMS X"
```

### Identification (Matching)
```yaml
detection:
  file_extension: ".xlsx" # ou .csv, .pdf
  filename_pattern: "^Export_.*_.*\\.xlsx$"
  required_headers: ["N° Site", "Date/Heure", "Libellé Événement"]
  # required_text: ["Signature PDF spécifique"] # pour les PDF
```

### Options Spécifiques aux Formats
```yaml
excel_options:
  sheet_name: "Feuille1" # ou sheet_index: 0
  header_row: 0          # Ligne des entêtes (0-based)
  skip_rows: 0           # Lignes à ignorer au début

csv_options:
  delimiter: ";"
  encoding: "utf-8"
  decimal_separator: ","
  thousands_separator: " "
```

### Mapping Canonique
```yaml
mapping:
  site_code: "N° Site"
  raw_timestamp: "Date/Heure"
  action_label: "Type Action"
  event_code: "Code"
  zone: "Zone / Partition"
  client_name: "Nom Client"
```

---

## 2. Validation & Matching

### Validator de Schéma
Au démarrage du backend, chaque profil est validé contre un schéma Pydantic. Si un profil est invalide (mapping manquant, extension inconnue), une erreur explicite est logguée et le profil est ignoré.

### ProfileMatcher
1. **Filtrage par Extension** : Seuls les profils correspondant à l'extension du fichier sont considérés.
2. **Scan des Headers** : Pour les fichiers Excel/CSV, les headers sont comparés aux `required_headers`.
3. **Calcul du Score** : Le matcher attribue des points (headers trouvés + pattern de nom matché).
4. **Tie-Break** : En cas de score identique, le profil avec la `priority` la plus élevée est choisi.
5. **Désambiguïsation** : Si deux profils ont le même score et la même priorité, le fichier est marqué **UNMATCHED**.

---

## 3. Idempotence Universelle

L'idempotence est garantie par le `event_hash`. 
**Calcul unique** : `SHA256(tenant_id + site_code + timestamp_utc + event_code + normalized_action)`.

> [!IMPORTANT]
> Le hash doit être indépendant de l'adapter. Un même fichier envoyé par email ou déposé dans Dropbox doit produire des événements avec des hashs identiques.
