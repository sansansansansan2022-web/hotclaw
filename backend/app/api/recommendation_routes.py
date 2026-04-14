"""Account recommendation APIs for pre-generation discovery."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.compose_preview import (
    ComposeSelectionSessionResponse,
    SelectedReferenceSourceResponse,
    SelectedSourceResponse,
)
from app.schemas.recommendation import (
    RecommendationCoverageResponse,
    RecommendationFilterDiagnosticsResponse,
    RecommendationListResponse,
    RecommendationSourceDiagnosticResponse,
    RecommendationShortageNoticeResponse,
    RecommendationSelectRequest,
    RecommendationSelectResponse,
    RecommendedContentItemResponse,
)
from app.services.compose_preview_service import compose_preview_service
from app.services.compose_selection_service import compose_selection_service
from app.services.recommendation_service import recommendation_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts/{account_id}/recommendations", tags=["recommendations"])


def _to_bucketed_response(
    *,
    account_id: str,
    rows,
    source_type: str | None,
    sort_by: str,
    status: str | None,
    total: int,
    refreshed_at,
    min_count: int,
    diagnostics: dict | None = None,
) -> RecommendationListResponse:
    bucketed = recommendation_service.bucketize_rows(rows, min_count=min_count, diagnostics=diagnostics)
    summary = recommendation_service.build_list_summary(rows)
    summary["high_relevance_count"] = bucketed["coverage"]["high_relevance_count"]
    summary["extended_count"] = bucketed["coverage"]["extended_count"]
    return RecommendationListResponse(
        account_id=account_id,
        filters={
            "source_type": source_type,
            "sort_by": sort_by,
            "status": status,
        },
        summary=summary,
        min_count=bucketed["min_count"],
        high_relevance_items=[
            RecommendedContentItemResponse(**recommendation_service.serialize_item(row))
            for row in bucketed["high_relevance_items"]
        ],
        extended_items=[
            RecommendedContentItemResponse(**recommendation_service.serialize_item(row))
            for row in bucketed["extended_items"]
        ],
        total=total,
        coverage=RecommendationCoverageResponse(**bucketed["coverage"]),
        shortage_notice=RecommendationShortageNoticeResponse(**bucketed["shortage_notice"]),
        source_diagnostics=[
            RecommendationSourceDiagnosticResponse(**item)
            for item in bucketed["source_diagnostics"]
        ],
        filter_diagnostics=RecommendationFilterDiagnosticsResponse(**bucketed["filter_diagnostics"]),
        refreshed_at=refreshed_at,
    )


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    account_id: str,
    source_type: str | None = Query(default=None),
    sort_by: str = Query(default="relevance", pattern="^(relevance|freshness)$"),
    status: str | None = Query(default=None),
    min_count: int = Query(default=5),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows, total, refreshed_at, diagnostics = await recommendation_service.list_recommendations(
            account_id,
            db,
            source_type=source_type,
            sort_by=sort_by,
            status=status,
        )
        return _to_bucketed_response(
            account_id=account_id,
            rows=rows,
            source_type=source_type,
            sort_by=sort_by,
            status=status,
            total=total,
            refreshed_at=refreshed_at,
            min_count=min_count,
            diagnostics=diagnostics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("recommendation_list_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to load recommendations")


@router.post("/refresh", response_model=RecommendationListResponse)
async def refresh_recommendations(
    account_id: str,
    min_count: int = Query(default=5),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await recommendation_service.refresh_recommendations(account_id, db)
        await db.commit()
        rows = result["rows"]
        return _to_bucketed_response(
            account_id=account_id,
            rows=rows,
            source_type=None,
            sort_by="relevance",
            status=None,
            total=len(rows),
            refreshed_at=result.get("refreshed_at"),
            min_count=min_count,
            diagnostics=result.get("diagnostics") or {},
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("recommendation_refresh_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to refresh recommendations")


@router.post("/select", response_model=RecommendationSelectResponse)
async def select_recommendations(
    account_id: str,
    req: RecommendationSelectRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        (
            session,
            selected_recommendations,
            selected_reference_sources,
        ) = await compose_selection_service.apply_recommendation_action(
            account_id=account_id,
            recommendation_ids=req.recommendation_ids,
            action=req.action,
            selection_session_id=req.selection_session_id,
            db=db,
        )
        await db.commit()
        if session is not None:
            await db.refresh(session)
        return RecommendationSelectResponse(
            selection_session=ComposeSelectionSessionResponse(**compose_selection_service.serialize_session(session))
            if session
            else None,
            selected_recommendations=[
                SelectedSourceResponse(**item)
                for item in compose_preview_service.serialize_selected_sources(selected_recommendations)
            ],
            selected_reference_sources=[
                SelectedReferenceSourceResponse(**item)
                for item in compose_selection_service.serialize_reference_sources(selected_reference_sources)
            ],
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("recommendation_select_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to update recommendation selection")
