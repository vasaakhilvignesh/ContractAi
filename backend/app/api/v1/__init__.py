"""
ContractIQ — API v1 Package
"""

from app.api.v1.contracts import router as contracts_router
from app.api.v1.analyst import router as analyst_router
from app.api.v1.comparison import router as comparison_router
from app.api.v1.obligations import router as obligations_router

__all__ = [
    "contracts_router",
    "analyst_router",
    "comparison_router",
    "obligations_router",
]
