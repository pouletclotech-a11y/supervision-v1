import re
import logging
from typing import List, Tuple, Optional
from pathlib import Path
from app.schemas.ingestion_profile import IngestionProfile
from app.ingestion.profile_manager import ProfileManager

logger = logging.getLogger("profile-matcher")

class ProfileMatcher:
    def __init__(self, manager: ProfileManager):
        self.manager = manager

    def match(self, file_path: str, headers: List[str] = None, text_content: str = None) -> Optional[IngestionProfile]:
        """
        Matches a file against loaded profiles using multiple criteria.
        Returns the best matching IngestionProfile or None.
        """
        path_obj = Path(file_path)
        ext = path_obj.suffix.lower()
        filename = path_obj.name
        
        candidates: List[Tuple[float, IngestionProfile]] = []

        for profile in self.manager.list_profiles():
            # 1. Filtre dur par extension
            if profile.detection.extensions and ext not in profile.detection.extensions:
                continue
            
            # Score de base si l'extension match
            score = 1.0
            
            # 2. Matching par pattern de nom de fichier (+5 points)
            if profile.detection.filename_pattern:
                if re.search(profile.detection.filename_pattern, filename, re.IGNORECASE):
                    score += 5.0
                else:
                    # Si un pattern est défini mais ne match pas, on peut considérer 
                    # soit un malus, soit l'exclusion selon la sévérité voulue.
                    # Ici on continue juste si le pattern est obligatoire.
                    pass

            # 3. Matching par headers (+1 point par header matché)
            if headers and profile.detection.required_headers:
                match_count = 0
                for req_h in profile.detection.required_headers:
                    if any(req_h.lower() in (h or "").lower() for h in headers):
                        match_count += 1
                        score += 1.0
                
                # Si TOUS les headers requis sont absents (et qu'il y en a de définis), 
                # on pénalise fortement.
                if profile.detection.required_headers and match_count == 0:
                    score -= 10.0

            # 4. Matching par contenu texte (PDF/TXT) (+3 points par mot-clé)
            if text_content and profile.detection.required_text:
                for req_txt in profile.detection.required_text:
                    if req_txt.lower() in text_content.lower():
                        score += 3.0

            if score > 0:
                candidates.append((score, profile))

        if not candidates:
            logger.info(f"Aucun profil matché pour {filename}")
            return None

        # --- TIE-BREAKING LOGIC ---
        # 1. Trier par Score (desc)
        # 2. Trier par Priorité (desc)
        # 3. Trier par ID de profil (asc) pour un tie-break déterministe
        
        candidates.sort(key=lambda x: (-x[0], -x[1].priority, x[1].profile_id))
        
        best_score, best_profile = candidates[0]
        
        # Détection d'ambiguïté (si les deux meilleurs ont même score ET même priorité)
        if len(candidates) > 1:
            next_score, next_profile = candidates[1]
            if best_score == next_score and best_profile.priority == next_profile.priority:
                logger.warning(
                    f"AMBIGUÏTÉ de matching pour {filename} : "
                    f"'{best_profile.profile_id}' vs '{next_profile.profile_id}' "
                    f"(Score: {best_score}, Prio: {best_profile.priority}). "
                    f"Utilisation du premier par défaut."
                )
                # On pourrait retourner None (UNMATCHED) ici si on veut une règle stricte
        
        logger.debug(f"Fichier {filename} matché avec le profil '{best_profile.profile_id}' (Score: {best_score})")
        return best_profile
