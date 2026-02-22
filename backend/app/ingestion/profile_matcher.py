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

    def match(self, file_path: str, headers: List[str] = None, text_content: str = None) -> Tuple[Optional[IngestionProfile], dict]:
        """
        Matches a file against loaded profiles using multiple criteria.
        Returns Tuple(Best Profile or None, Match Report).
        """
        path_obj = Path(file_path)
        ext = path_obj.suffix.lower()
        filename = path_obj.name
        
        candidates: List[Tuple[float, IngestionProfile]] = []
        match_report = {
            "filename": filename,
            "candidates": [],
            "best_profile": None,
            "best_score": 0.0,
            "threshold_met": False
        }

        logger.info(f"--- START MATCHING for {filename} ---")

        for profile in self.manager.list_profiles():
            # 1. Hard Filter by extension
            if profile.detection.extensions and ext not in profile.detection.extensions:
                continue
            
            # Base score if extension matches
            score = 1.0
            details = [f"Extension {ext} match (+1.0)"]
            
            # 2. Filename pattern matching (+5.0)
            if profile.detection.filename_pattern:
                if re.search(profile.detection.filename_pattern, filename, re.IGNORECASE):
                    score += 5.0
                    details.append(f"Filename pattern '{profile.detection.filename_pattern}' match (+5.0)")
            
            # 3. Headers matching (+1.0 per header)
            if profile.detection.required_headers:
                if headers is not None:
                    h_matches = 0
                    for req_h in profile.detection.required_headers:
                        if any(req_h.lower() in (h or "").lower() for h in headers):
                            h_matches += 1
                    
                    if h_matches > 0:
                        score += float(h_matches)
                        details.append(f"{h_matches}/{len(profile.detection.required_headers)} headers match (+{float(h_matches)})")
                    else:
                        score -= 10.0 # Heavy penalty if required headers don't match
                        details.append("REQUIRED HEADERS MISMATCH (-10.0)")
            
            # 4. Text content matching (+3.0 per keyword)
            if profile.detection.required_text:
                if text_content is not None:
                    t_matches = 0
                    for req_txt in profile.detection.required_text:
                        if req_txt.lower() in text_content.lower():
                            t_matches += 1
                    
                    if t_matches > 0:
                        score += float(t_matches * 3.0)
                        details.append(f"{t_matches}/{len(profile.detection.required_text)} text keywords match (+{float(t_matches * 3.0)})")
                    else:
                        score -= 10.0 # Heavy penalty
                        details.append("REQUIRED TEXT MISMATCH (-10.0)")

            threshold = profile.confidence_threshold or 2.0
            is_valid = score >= threshold
            
            cand_info = {
                "profile_id": profile.profile_id,
                "score": score,
                "threshold": threshold,
                "is_valid": is_valid,
                "details": details
            }
            match_report["candidates"].append(cand_info)
            
            logger.info(f"Candidat: {profile.profile_id} | Score: {score:.2f} | Seuil: {threshold} | Valide: {'OK' if is_valid else 'KO'}")

            if is_valid:
                candidates.append((score, profile))

        if not candidates:
            logger.warning(f"AUCUN PROFIL CONFIDENT trouvé pour {filename}")
            # Find best even if not confident for reporting
            all_cands = sorted(match_report["candidates"], key=lambda x: x["score"], reverse=True)
            if all_cands:
                match_report["best_score"] = all_cands[0]["score"]
                match_report["best_candidate_id"] = all_cands[0]["profile_id"]
            return None, match_report

        # TIE-BREAKING
        candidates.sort(key=lambda x: (-x[0], -x[1].priority, x[1].profile_id))
        best_score, best_profile = candidates[0]
        
        match_report["best_profile"] = best_profile.profile_id
        match_report["best_score"] = best_score
        match_report["threshold_met"] = True
        
        logger.info(f"MATCH RETENU : {best_profile.profile_id} (Score: {best_score:.2f})")
        return best_profile, match_report
