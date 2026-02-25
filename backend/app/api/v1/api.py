from fastapi import APIRouter, Depends
from app.api.v1.endpoints import (
    imports, events, alerts, settings, utils, login, users, debug, connections,
    admin_unmatched, admin_profiles, admin_sandbox, admin_reprocess, admin_business, admin_providers
)
from app.auth import deps

api_router = APIRouter()
api_router.include_router(login.router, prefix="/auth", tags=["auth"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"], dependencies=[Depends(deps.get_current_user)])
api_router.include_router(events.router, prefix="/events", tags=["events"], dependencies=[Depends(deps.get_current_user)])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"], dependencies=[Depends(deps.get_current_user)])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"], dependencies=[Depends(deps.get_current_operator_or_admin)])
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=[Depends(deps.get_current_user)])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])

# Admin Calibration Tool (Phase 3 BIS)
api_router.include_router(admin_unmatched.router, prefix="/admin/unmatched", tags=["admin-calibration"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(admin_profiles.router, prefix="/admin/profiles", tags=["admin-calibration"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(admin_sandbox.router, prefix="/admin/sandbox", tags=["admin-calibration"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(admin_reprocess.router, prefix="/admin/reprocess", tags=["admin-calibration"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(admin_business.router, prefix="/admin/business", tags=["admin-business"], dependencies=[Depends(deps.get_current_active_admin)])
api_router.include_router(admin_providers.router, prefix="/admin/providers", tags=["admin-providers"], dependencies=[Depends(deps.get_current_active_admin)])
