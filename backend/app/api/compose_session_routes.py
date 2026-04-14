"""Compose selection session APIs for the new creation flow."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError, AccountInactiveError, AccountValidationError, TaskAlreadyExistsError, TaskCreateError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.account import AccountRunData
from app.schemas.compose_preview import (
    ComposeOutlineConfirmationRequest,
    ComposeSourceConfirmationRequest,
    ComposeReferenceSourceSelectionRequest,
    ComposeSelectionSessionBundleResponse,
    ComposeSelectionSessionCreateRequest,
    ComposeSelectionSessionResponse,
    ComposeSubmitRequest,
    SelectedReferenceSourceResponse,
    SelectedSourceResponse,
)
from app.services.account_run_dispatch_service import account_run_dispatch_service
from app.services.account_service import account_service
from app.services.compose_preview_service import compose_preview_service
from app.services.compose_selection_service import compose_selection_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts/{account_id}/selection-sessions", tags=["compose-sessions"])


def _to_bundle_response(
    session,
    *,
    selected_recommendations: list[dict],
    selected_reference_sources: list[dict],
) -> ComposeSelectionSessionBundleResponse:
    return ComposeSelectionSessionBundleResponse(
        selection_session=ComposeSelectionSessionResponse(
            **compose_selection_service.serialize_session(session)
        ),
        selected_recommendations=[
            SelectedSourceResponse(**item) for item in selected_recommendations
        ],
        selected_reference_sources=[
            SelectedReferenceSourceResponse(**item)
            for item in selected_reference_sources
        ],
    )


@router.post("", response_model=ComposeSelectionSessionBundleResponse, status_code=201)
async def create_selection_session(
    account_id: str,
    req: ComposeSelectionSessionCreateRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        session = await compose_selection_service.get_or_create_session(account_id, db)
        if req:
            session = await compose_selection_service.update_session_preferences(
                account_id,
                session.id,
                db,
                creation_note=req.creation_note,
                preferred_lane=req.preferred_lane,
                title_direction=req.title_direction,
            )
            if req.reference_source_ids:
                session, selected_reference_sources = await compose_selection_service.replace_selected_reference_sources(
                    account_id=account_id,
                    session_id=session.id,
                    reference_source_ids=req.reference_source_ids,
                    db=db,
                )
            else:
                selected_reference_sources = []
        else:
            selected_reference_sources = []

        selected_recommendations = await compose_selection_service.list_selected_recommendations(
            account_id,
            session,
            db,
        )
        if not selected_reference_sources:
            selected_reference_sources = await compose_selection_service.list_selected_reference_sources(
                account_id,
                session,
                db,
            )
        await db.commit()
        await db.refresh(session)
        return _to_bundle_response(
            session,
            selected_recommendations=compose_preview_service.serialize_selected_sources(
                selected_recommendations
            ),
            selected_reference_sources=compose_selection_service.serialize_reference_sources(
                selected_reference_sources
            ),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("compose_selection_session_create_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to create selection session")


@router.get("/{selection_session_id}", response_model=ComposeSelectionSessionBundleResponse)
async def get_selection_session(
    account_id: str,
    selection_session_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        session, selected_recommendations, selected_reference_sources = await compose_selection_service.load_session_bundle(
            account_id,
            selection_session_id,
            db,
        )
        return _to_bundle_response(
            session,
            selected_recommendations=compose_preview_service.serialize_selected_sources(
                selected_recommendations
            ),
            selected_reference_sources=compose_selection_service.serialize_reference_sources(
                selected_reference_sources
            ),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("compose_selection_session_get_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to load selection session")


@router.post(
    "/{selection_session_id}/reference-sources/select",
    response_model=ComposeSelectionSessionBundleResponse,
)
async def select_reference_sources_for_creation(
    account_id: str,
    selection_session_id: str,
    req: ComposeReferenceSourceSelectionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        session, selected_reference_sources = await compose_selection_service.replace_selected_reference_sources(
            account_id=account_id,
            session_id=selection_session_id,
            reference_source_ids=req.reference_source_ids,
            db=db,
        )
        selected_recommendations = await compose_selection_service.list_selected_recommendations(
            account_id,
            session,
            db,
        )
        await db.commit()
        await db.refresh(session)
        return _to_bundle_response(
            session,
            selected_recommendations=compose_preview_service.serialize_selected_sources(
                selected_recommendations
            ),
            selected_reference_sources=compose_selection_service.serialize_reference_sources(
                selected_reference_sources
            ),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "compose_selection_reference_select_error",
            account_id=account_id,
            selection_session_id=selection_session_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to update selected reference sources")


@router.post("/{selection_session_id}/confirm-sources", response_model=ComposeSelectionSessionBundleResponse)
async def confirm_selection_sources(
    account_id: str,
    selection_session_id: str,
    req: ComposeSourceConfirmationRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        if not req.confirmed:
            raise ValueError("confirmed must be true")
        session = await compose_selection_service.confirm_sources(account_id, selection_session_id, db)
        selected_recommendations = await compose_selection_service.list_selected_recommendations(
            account_id,
            session,
            db,
        )
        selected_reference_sources = await compose_selection_service.list_selected_reference_sources(
            account_id,
            session,
            db,
        )
        await db.commit()
        await db.refresh(session)
        return _to_bundle_response(
            session,
            selected_recommendations=compose_preview_service.serialize_selected_sources(
                selected_recommendations
            ),
            selected_reference_sources=compose_selection_service.serialize_reference_sources(
                selected_reference_sources
            ),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "compose_selection_confirm_sources_error",
            account_id=account_id,
            selection_session_id=selection_session_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to confirm selected sources")


@router.post("/{selection_session_id}/confirm-outline", response_model=ComposeSelectionSessionResponse)
async def confirm_selection_outline(
    account_id: str,
    selection_session_id: str,
    req: ComposeOutlineConfirmationRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        session = await compose_selection_service.confirm_outline(
            account_id,
            selection_session_id,
            preview_version=req.preview_version,
            approved_outline_seed=req.approved_outline_seed,
            db=db,
        )
        await db.commit()
        await db.refresh(session)
        return ComposeSelectionSessionResponse(
            **compose_selection_service.serialize_session(session)
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "compose_selection_confirm_outline_error",
            account_id=account_id,
            selection_session_id=selection_session_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to confirm outline")


@router.post("/{selection_session_id}/submit", response_model=AccountRunData)
async def submit_selection_session_for_generation(
    account_id: str,
    selection_session_id: str,
    req: ComposeSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await account_service.get_account(account_id, db)
        session = await compose_selection_service.validate_submit_ready(
            account_id,
            selection_session_id,
            db,
        )
        if req.creation_note is not None and (req.creation_note.strip() or None) != session.creation_note:
            raise ValueError("creation_note changed after preview; regenerate and confirm the outline again")
        if req.preferred_lane is not None and (req.preferred_lane.strip() or None) != session.preferred_lane:
            raise ValueError("preferred_lane changed after preview; regenerate and confirm the outline again")
        if req.title_direction is not None and (req.title_direction.strip() or None) != session.title_direction:
            raise ValueError("title_direction changed after preview; regenerate and confirm the outline again")

        preview_bundle = await compose_preview_service.build_submit_bundle(
            account_id=account_id,
            selection_session_id=selection_session_id,
            db=db,
        )
        explicit_input = preview_bundle["runtime_payload"]
        account, task = await account_service.run_account(
            account_id,
            db,
            allow_auto=False,
            explicit_input=explicit_input,
        )
        await compose_selection_service.update_session_preferences(
            account_id,
            selection_session_id,
            db,
            status="submitted",
        )
        await db.commit()
        account_run_dispatch_service.schedule(task_id=task.id, account_id=account.id)
        return AccountRunData(
            **account_service.build_account_run_payload(
                account,
                task,
                selection_session_id=selection_session_id,
            )
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AccountInactiveError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    except AccountValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    except TaskAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    except TaskCreateError as exc:
        raise HTTPException(status_code=500, detail=exc.message)
    except Exception as exc:
        logger.error(
            "compose_selection_submit_error",
            account_id=account_id,
            selection_session_id=selection_session_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to submit generation")
