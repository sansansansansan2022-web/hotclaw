import pytest

from app.services.schema_guard_service import SchemaGuardReport, SchemaGuardService


@pytest.mark.asyncio
async def test_schema_guard_allows_revision_mismatch_only_when_structure_is_ready():
    service = SchemaGuardService()
    report = SchemaGuardReport(
        current_revisions=("20260414_0006",),
        head_revisions=("20260414_0008",),
    )

    async def inspect_runtime_schema():
        return report

    service.inspect_runtime_schema = inspect_runtime_schema

    allowed = await service.assert_runtime_schema(allow_revision_mismatch=True)
    assert allowed is report

    with pytest.raises(RuntimeError, match="alembic revision mismatch"):
        await service.assert_runtime_schema()


@pytest.mark.asyncio
async def test_schema_guard_still_blocks_missing_columns_when_revision_mismatch_is_allowed():
    service = SchemaGuardService()
    report = SchemaGuardReport(
        current_revisions=("20260414_0006",),
        head_revisions=("20260414_0008",),
        missing_columns={"accounts": ["content_platform"]},
    )

    async def inspect_runtime_schema():
        return report

    service.inspect_runtime_schema = inspect_runtime_schema

    with pytest.raises(RuntimeError, match="missing columns"):
        await service.assert_runtime_schema(allow_revision_mismatch=True)
