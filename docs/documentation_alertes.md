# Guide de Programmation des Alertes - Supervision V1

Ce document vous explique comment configurer les règles d'alerte pour surveiller les événements de vos prestataires.

## 1. Aide à la Saisie : Assistant Catalogue (V4)

Depuis l'écran de création de règles, utilisez le bouton **"Aide Catalogue"**. 
Un panneau latéral s'ouvre, vous permettant de :
- Rechercher un code d'alarme.
- Voir son **Label Canonique (La Vérité)** : Un libellé épuré, garanti **100% invariant** (seuls les mots qui reviennent systématiquement sont gardés) et débarrassé des mots techniques (`APPARITION`, `DISPARITION`).
- Cliquer sur **"Sélectionner"** pour remplir automatiquement le mot-clé et la catégorie.

---

## 2. Configuration Générale (Mode Simple)

Le mode **Simple** permet de déclencher une alerte lorsqu'un mot-clé apparaît un certain nombre de fois.

### Glossaire des champs :
- **Rule Name** : Nom unique de l'alerte.
- **Match Category** : Filtre sur la catégorie (ex: `COM`, `ALM`, `SEC`). *Note: Correspond au champ `category` en base de données.*
- **Match Keyword** : Le texte précis recherché. *Note: Correspond au champ `normalized_message` (épuré).*
- **Sliding Window (Days)** : Profondeur d'analyse temporelle.
- **Min Occurrences** : Nombre de répétitions requis pour alerter.
- **Window (sec)** : Temps maximum pour atteindre ces occurrences.

---

## 3. Mode Séquence (A ➔ B)

Le mode **Séquence** surveille l'intervalle entre deux événements liés par le même code site et code alarme.

### Exemple : Détection de retard de disparition
1. **A : Keyword** = Mot-clé d'Apparition.
2. **B : Keyword** = Mot-clé de Disparition.
3. **Max Delay (sec)** : Temps d'attente maximum avant de considérer qu'il y a une anomalie.

---

## 4. Replay & Mise à Jour
- **Bouton Replay Rules** : Indispensable après toute modification de règle pour recalculer l'historique.
- **Atomicité** : Le système remplace proprement les anciennes alertes (`AlertHit`) par les nouvelles pour éviter les doublons.

---

## ⚠️ Rappel sur la "Vérité" du Catalogue
Le catalogue V4 a été durci (Mars 2026) :
- Si un code (ex: `$0001`) n'a aucun noyau textuel commun à 100%, le système affiche `CODE $0001` par sécurité pour ne pas induire en erreur.
- La performance a été optimisée par indexation SQL pour une réponse en moins de 15s sur des volumes massifs.
