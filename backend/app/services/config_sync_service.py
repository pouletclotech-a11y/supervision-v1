import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import MonitoringProvider, DBIngestionProfile, ProfileRevision
from app.schemas.config_schema import (
    ConfigExportSchema, ProviderConfigSchema, ProfileConfigSchema,
    ImportSummarySchema, ImportDiffItem
)

logger = logging.getLogger("config-sync")

class ConfigSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_config(self) -> ConfigExportSchema:
        """Export all providers and profiles to a structured schema."""
        # 1. Fetch Providers
        stmt_prov = select(MonitoringProvider).order_by(MonitoringProvider.code)
        res_prov = await self.db.execute(stmt_prov)
        db_providers = res_prov.scalars().all()
        
        providers = [
            ProviderConfigSchema.model_validate(p, from_attributes=True)
            for p in db_providers
        ]
        
        # 2. Fetch Profiles
        stmt_prof = select(DBIngestionProfile).order_by(DBIngestionProfile.profile_id)
        res_prof = await self.db.execute(stmt_prof)
        db_profiles = res_prof.scalars().all()
        
        profiles = [
            ProfileConfigSchema.model_validate(p, from_attributes=True)
            for p in db_profiles
        ]
        
        return ConfigExportSchema(
            version="1.0",
            exported_at=datetime.now(),
            providers=providers,
            profiles=profiles
        )

    async def import_config(
        self, 
        config: ConfigExportSchema, 
        dry_run: bool = True, 
        mode: str = "merge",
        user_id: int = None
    ) -> ImportSummarySchema:
        """
        Import configuration with dry-run and merge/replace options.
        Transactional logic ensures safety.
        """
        summary = ImportSummarySchema()
        
        try:
            # --- 1. PROVIDERS SYNC ---
            # Map existing providers by code
            stmt_exist_prov = select(MonitoringProvider)
            res_exist_prov = await self.db.execute(stmt_exist_prov)
            db_providers = {p.code: p for p in res_exist_prov.scalars().all()}
            
            incoming_prov_codes = {p.code for p in config.providers}
            
            for p_in in config.providers:
                if p_in.code in db_providers:
                    # Check for updates (simplified comparison)
                    db_p = db_providers[p_in.code]
                    needs_update = self._check_provider_needs_update(db_p, p_in)
                    
                    if needs_update:
                        summary.updated += 1
                        summary.diff.append(ImportDiffItem(key=p_in.code, action="UPDATE"))
                        if not dry_run:
                            for field, value in p_in.model_dump().items():
                                setattr(db_p, field, value)
                    else:
                        summary.unchanged += 1
                        summary.diff.append(ImportDiffItem(key=p_in.code, action="UNCHANGED"))
                else:
                    # Create NEW
                    summary.created += 1
                    summary.diff.append(ImportDiffItem(key=p_in.code, action="CREATE"))
                    if not dry_run:
                        new_p = MonitoringProvider(**p_in.model_dump())
                        self.db.add(new_p)

            # SOFT-DISABLE for replace mode
            if mode == "replace":
                for code, db_p in db_providers.items():
                    if code not in incoming_prov_codes and db_p.is_active:
                        summary.disabled += 1
                        summary.diff.append(ImportDiffItem(key=code, action="DISABLE", details="Not in source"))
                        if not dry_run:
                            db_p.is_active = False

            # --- 2. PROFILES SYNC ---
            stmt_exist_prof = select(DBIngestionProfile)
            res_exist_prof = await self.db.execute(stmt_exist_prof)
            db_profiles = {p.profile_id: p for p in res_exist_prof.scalars().all()}
            
            incoming_prof_ids = {p.profile_id for p in config.profiles}
            
            for p_in in config.profiles:
                if p_in.profile_id in db_profiles:
                    db_p = db_profiles[p_in.profile_id]
                    needs_update = self._check_profile_needs_update(db_p, p_in)
                    
                    if needs_update:
                        summary.updated += 1
                        summary.diff.append(ImportDiffItem(key=p_in.profile_id, action="UPDATE"))
                        if not dry_run:
                            update_data = p_in.model_dump()
                            for field, value in update_data.items():
                                setattr(db_p, field, value)
                            # Audit Revision is complex, skipped for baseline but recommended for prod
                    else:
                        summary.unchanged += 1
                        summary.diff.append(ImportDiffItem(key=p_in.profile_id, action="UNCHANGED"))
                else:
                    summary.created += 1
                    summary.diff.append(ImportDiffItem(key=p_in.profile_id, action="CREATE"))
                    if not dry_run:
                        new_p = DBIngestionProfile(**p_in.model_dump())
                        self.db.add(new_p)

            if mode == "replace":
                for pid, db_p in db_profiles.items():
                    if pid not in incoming_prof_ids and db_p.is_active:
                        summary.disabled += 1
                        summary.diff.append(ImportDiffItem(key=pid, action="DISABLE", details="Not in source"))
                        if not dry_run:
                            db_p.is_active = False

            if not dry_run:
                # Add Audit Log (simplified)
                logger.info(f"Config Import committed by user_id={user_id}. Mode={mode}, Created={summary.created}, Updated={summary.updated}")
                await self.db.commit()
            else:
                await self.db.rollback() # Ensure dry_run never commits

        except Exception as e:
            logger.error(f"Config Import Failed: {e}", exc_info=True)
            summary.errors.append(str(e))
            await self.db.rollback()
            
        return summary

    def _check_provider_needs_update(self, db_obj: MonitoringProvider, schema_obj: ProviderConfigSchema) -> bool:
        """Compare DB object with schema to see if updates are required."""
        data = schema_obj.model_dump()
        for k, v in data.items():
            db_val = getattr(db_obj, k, None)
            if db_val != v:
                return True
        return False

    def _check_profile_needs_update(self, db_obj: DBIngestionProfile, schema_obj: ProfileConfigSchema) -> bool:
        data = schema_obj.model_dump()
        for k, v in data.items():
            if k in ["created_at", "updated_at", "version_number", "id"]:
                continue
            db_val = getattr(db_obj, k, None)
            if db_val != v:
                return True
        return False
