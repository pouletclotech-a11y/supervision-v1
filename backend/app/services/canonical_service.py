import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("canonical-service")

# Liste des tokens d'état à exclure du label canonique (Bruit technique)
STATE_TOKENS = {
    'APPARITION', 'DISPARITION', 'DEBUT', 'FIN', 'ALESTE', 'ALERTE', 
    'RETOUR', 'NORMALE', 'ETAT', 'STATION', 'CENTRAL', 'APP', 'DISP',
    'MESSAGE', 'SANS', 'EVENEMENT', 'ENTREE', 'SORTIE'
}

def tokenize(text: str) -> List[str]:
    """
    Découpe le texte en tokens épurés (majuscules, sans nombres, sans ponctuation).
    Supprime les tokens purement numériques, trop courts, ou faisant partie des mots d'état.
    """
    if not text:
        return []
    
    # Remplacer tout ce qui n'est pas lettre par un espace
    cleaned = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # Découpage et mise en majuscules
    tokens = []
    for t in cleaned.split():
        t = t.strip().upper()
        # On garde les tokens non numériques de plus de 1 caractère (ex: "IP" est important)
        # ET qui ne sont pas des mots d'état
        if t and not t.isdigit() and len(t) >= 2 and t not in STATE_TOKENS:
            tokens.append(t)
            
    return tokens

def get_canonical_label(variants: List[Dict[str, Any]], code: Optional[str] = None, threshold: float = 1.0) -> Dict[str, Any]:
    """
    Analyse une liste de variantes [ {'message': str, 'occurrences': int} ]
    pour en extraire un label stable et épuré.
    RÈGLE SÉBASTIEN : Uniquement les tokens présents dans >= threshold% des variantes.
    """
    total_occ = sum(v.get('occurrences', 0) for v in variants)
    if not variants or total_occ == 0:
        return {
            "label": f"CODE {code}" if code else "N/A", 
            "confidence": 0, 
            "most_frequent": "",
            "token_stats": []
        }

    # 1. Identifier le message le plus fréquent (base de l'ordre des tokens)
    sorted_variants = sorted(variants, key=lambda x: x.get('occurrences', 0), reverse=True)
    most_frequent = sorted_variants[0].get('message', '')
    
    # 2. Analyse de fréquence des tokens
    token_weights = {}
    for v in variants:
        msg = v.get('message', '')
        occ = v.get('occurrences', 0)
        unique_tokens = set(tokenize(msg))
        for t in unique_tokens:
            token_weights[t] = token_weights.get(t, 0) + occ
            
    # 3. Calcul des statistiques de tokens
    token_stats = []
    for t, weight in token_weights.items():
        pct = round(weight / total_occ, 3)
        token_stats.append({
            "token": t,
            "count": weight,
            "percentage": pct
        })
    # Trier par fréquence décroissante
    token_stats.sort(key=lambda x: x["percentage"], reverse=True)

    # 4. Extraction des tokens invariants (présents dans >= threshold * total_occ)
    base_tokens = tokenize(most_frequent)
    canonical_tokens = []
    
    for t in base_tokens:
        weight = token_weights.get(t, 0)
        if weight >= (threshold * total_occ):
            canonical_tokens.append(t)
            
    # 5. Fallback SI aucun token invariant n'est trouvé
    if not canonical_tokens:
        top_occ = sorted_variants[0].get('occurrences', 0)
        if top_occ / total_occ >= 0.8:
            clean_top = " ".join(tokenize(most_frequent))
            return {
                "label": clean_top or f"CODE {code}" if code else "ALERTE",
                "confidence": 0.5,
                "most_frequent": most_frequent,
                "token_stats": token_stats
            }
        
        return {
            "label": f"CODE {code}" if code else "ALERTE",
            "confidence": 0.2,
            "most_frequent": most_frequent,
            "token_stats": token_stats
        }

    label = " ".join(canonical_tokens)
    return {
        "label": label,
        "confidence": threshold, 
        "most_frequent": most_frequent,
        "token_stats": token_stats
    }
