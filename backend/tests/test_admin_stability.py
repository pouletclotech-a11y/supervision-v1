import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import text
from app.main import init_tables
from app.core.config import settings

@pytest.mark.asyncio
async def test_init_tables_skips_create_all_in_prod():
    """Vérifie que Base.metadata.create_all n'est PAS appelé si ENVIRONMENT=production."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.AUTO_SEED_ADMIN = False
        
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock()
        
        with patch("app.main.engine", mock_engine):
            await init_tables()
            
            # create_all ne doit pas avoir été appelé
            mock_engine.begin.assert_not_called()

@pytest.mark.asyncio
async def test_seed_admin_skips_if_table_missing():
    """Vérifie que le seed s'arrête proprement si la table users n'existe pas."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.AUTO_SEED_ADMIN = True
        
        # Mock engine.connect() pour simuler l'échec de la requête brute SELECT 1 FROM users
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("Table users not found")
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        
        with patch("app.main.engine", mock_engine):
            with patch("app.main.perform_admin_seed") as mock_seed:
                await init_tables()
                mock_seed.assert_not_called()

@pytest.mark.asyncio
async def test_seed_admin_triggers_if_no_admin():
    """Vérifie que le seed est déclenché si la table existe mais aucun admin n'est présent."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "development"
        mock_settings.AUTO_SEED_ADMIN = True
        mock_settings.DEFAULT_ADMIN_EMAIL = "test@admin.com"
        mock_settings.DEFAULT_ADMIN_PASSWORD = "Password123"
        
        # 1. Mock engine.connect pour dire que la table existe
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None # Pas d'exception
        
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

        # 2. Mock DB check pour dire qu'il n'y a pas d'admin
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [] # Aucun admin
        
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        # Setup session context manager
        mock_session.__aenter__.return_value = mock_session
        
        # Mock AsyncSessionLocal to return our mock_session context manager
        mock_session_factory = MagicMock(return_value=mock_session)
        
        # Application des patchs
        with patch("app.main.engine", mock_engine):
            with patch("app.db.session.AsyncSessionLocal", mock_session_factory):
                with patch("app.main.perform_admin_seed", new_callable=AsyncMock) as mock_seed:
                    await init_tables()
                    mock_seed.assert_called_once_with("test@admin.com", "Password123")
