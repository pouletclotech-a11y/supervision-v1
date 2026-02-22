# Spécification : Input Adapters

Les **Input Adapters** sont les composants chargés de la capture des fichiers sources. Ils extraient les données brutes depuis divers canaux (Email, Dropbox, API) et les transmettent au pipeline de normalisation.

---

## 1. Architecture des Adapters

Chaque adapter doit implémenter l'interface canonique `BaseAdapter` définie dans `backend/app/ingestion/adapters/base.py`.

```python
class BaseAdapter:
    async def fetch(self) -> List[RawFile]:
        """Récupère les nouveaux fichiers depuis la source."""
        pass

    async def acknowledge(self, raw_file: RawFile):
        """Marque le fichier comme traité (archive, suppression, tag)."""
        pass
```

---

## 2. Adapters Supportés (Phase 1)

### DropboxIngressAdapter (`dropbox_in`)
- **Canal** : Système de fichiers local (watcher).
- **Fonctionnement** : Scanne périodiquement ou via événements OS le dossier `dropbox_in/`.
- **Acquittement** : Déplacement du fichier original vers `/archive/raw/{yyyy}/{mm}/{import_id}/`.

### EmailAttachmentAdapter
- **Canal** : Protocole IMAP.
- **Bookmark (Reprise après reboot)** : 
    - Chaque `message-id` traité est stocké en DB dans une table `processed_messages`.
    - L'adapter n'analyse que les messages dont l'UID est supérieur au dernier UID traité ou non présent en base.
- **Acquittement** : 
    - Marque le message comme `\Seen` (Lu).
    - Ajoute un flag `PROCESSED` (si supporté par le serveur) ou déplace le message dans un dossier d'archive spécialisé.

---

## 4. AdapterRegistry & Activation

L'activation des adapters est contrôlée dynamiquement par des variables d'environnement dans le `docker-compose.yml` :

```env
ADAPTER_DROPBOX_ENABLED=true
ADAPTER_EMAIL_ENABLED=true
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_USER=...
```

Le `AdapterRegistry` initialise uniquement les adapters marqués "Enabled" au démarrage du worker.

---

## 5. Critères de Robustesse
- **Tolérance aux pannes** : Si le serveur redémarre pendant un fetch, l'adapter doit reprendre là où il s'est arrêté (pas de double import).
- **Traçabilité** : Chaque `RawFile` doit conserver le nom de l'adapter source dans les métadonnées de l'import.
- **Sécurité** : Les credentials des adapters (IMAP, API) sont stockés dans les variables d'environnement (`.env`) et jamais en dur.
