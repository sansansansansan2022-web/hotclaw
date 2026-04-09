"""Routes for account onboarding workflows."""

from fastapi import APIRouter, HTTPException

from app.core.logger import get_logger
from app.schemas.account_onboarding import (
    ExistingAccountAnalysisRequest,
    ExistingAccountAnalysisResponse,
)
from app.services.account_onboarding_service import account_onboarding_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/account-onboarding", tags=["account-onboarding"])


@router.post("/analyze-existing", response_model=ExistingAccountAnalysisResponse)
async def analyze_existing_account(
    req: ExistingAccountAnalysisRequest,
):
    """Analyze historical materials for an existing public account without creating it yet."""
    try:
        return await account_onboarding_service.analyze_existing_account(req)
    except ValueError as exc:
        logger.warning("existing_account_analysis_invalid_request", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("existing_account_analysis_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="failed to analyze historical account materials")

