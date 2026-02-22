from fastapi import APIRouter, Depends
from app.api.v1.endpoints import imports, events, alerts, settings, utils, login, users, debug, connections
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
