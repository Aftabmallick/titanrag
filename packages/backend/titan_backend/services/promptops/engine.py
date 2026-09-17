from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.redis_client import get_redis
from titan_backend.db.models.promptops import PromptEnvironment, PromptTemplate, PromptVersion
from titan_backend.services.promptops.diff import count_tokens
from titan_backend.services.promptops.sandbox import sandbox

logger = structlog.get_logger(__name__)

# Local in-memory LRU cache
_PROMPT_CACHE: dict[str, str] = {}


class PromptOpsEngine:
    @staticmethod
    def _cache_key(workspace_id: UUID, slug: str, environment: PromptEnvironment) -> str:
        return f"prompt:{workspace_id}:{slug}:{environment.value}"

    @classmethod
    async def invalidate_cache(cls, workspace_id: UUID, slug: str, environment: PromptEnvironment) -> None:
        key = cls._cache_key(workspace_id, slug, environment)
        _PROMPT_CACHE.pop(key, None)
        try:
            redis = await get_redis()
            await redis.publish(f"promptops.invalidate:{slug}", f"{workspace_id}:{environment.value}")
        except Exception as e:
            logger.warning("failed_publishing_prompt_invalidation", error=str(e))

    @classmethod
    async def get_active_prompt(
        cls,
        session: AsyncSession,
        workspace_id: UUID,
        slug: str,
        environment: PromptEnvironment = PromptEnvironment.PROD,
    ) -> str | None:
        cache_key = cls._cache_key(workspace_id, slug, environment)
        if cache_key in _PROMPT_CACHE:
            return _PROMPT_CACHE[cache_key]

        stmt = (
            select(PromptVersion.content)
            .join(PromptTemplate, PromptTemplate.id == PromptVersion.template_id)
            .where(
                PromptTemplate.workspace_id == workspace_id,
                PromptTemplate.slug == slug,
                PromptVersion.environment == environment,
                PromptVersion.is_active,
            )
            .order_by(PromptVersion.version_number.desc())
            .limit(1)
        )
        res = (await session.execute(stmt)).scalar_one_or_none()
        if res is not None:
            _PROMPT_CACHE[cache_key] = res
        return res

    @classmethod
    async def create_version(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        slug: str,
        content: str,
        name: str | None = None,
        author_id: UUID | None = None,
        commit_message: str | None = None,
        environment: PromptEnvironment = PromptEnvironment.DEV,
        input_schema: dict[str, Any] | None = None,
    ) -> PromptVersion:
        # 1. Validate template syntax in sandbox
        sandbox.validate_template_syntax(content)

        # 2. Find or create parent template
        template_stmt = select(PromptTemplate).where(
            PromptTemplate.workspace_id == workspace_id,
            PromptTemplate.slug == slug,
        )
        template = (await session.execute(template_stmt)).scalar_one_or_none()
        if not template:
            template = PromptTemplate(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                slug=slug,
                name=name or slug.replace("_", " ").title(),
                description=f"Prompt template for {slug}",
            )
            session.add(template)
            await session.flush()

        # 3. Calculate next version number
        max_ver_stmt = select(func.coalesce(func.max(PromptVersion.version_number), 0)).where(
            PromptVersion.template_id == template.id
        )
        max_val = (await session.execute(max_ver_stmt)).scalar()
        next_ver = (int(max_val) if max_val is not None else 0) + 1

        token_est = count_tokens(content)

        version = PromptVersion(
            template_id=template.id,
            version_number=next_ver,
            content=content,
            input_schema=input_schema or {},
            environment=environment,
            author_id=author_id,
            commit_message=commit_message,
            is_active=False,
            token_count_estimate=token_est,
        )
        session.add(version)
        await session.commit()
        await session.refresh(version)
        return version

    @classmethod
    async def promote_version(
        cls,
        session: AsyncSession,
        template_id: UUID,
        version_number: int,
        target_environment: PromptEnvironment,
        force: bool = False,
    ) -> PromptVersion:
        template = await session.get(PromptTemplate, template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        target_stmt = select(PromptVersion).where(
            PromptVersion.template_id == template_id,
            PromptVersion.version_number == version_number,
        )
        version = (await session.execute(target_stmt)).scalar_one_or_none()
        if not version:
            raise ValueError(f"Version {version_number} not found for template {template_id}")

        # --- REGRESSION PROMOTION GATES ---
        if not force:
            # 1. Syntax validation gate
            sandbox.validate_template_syntax(version.content)

            # 2. Token count safety limit (max 8,000 tokens)
            if version.token_count_estimate and version.token_count_estimate > 8000:
                raise ValueError(
                    f"Promotion rejected by gatekeeper: Token count ({version.token_count_estimate}) "
                    f"exceeds maximum allowed safety limit (8000 tokens)."
                )

            # 3. Environment progression gate: Cannot deploy directly from DEV to PROD without STAGING
            if target_environment == PromptEnvironment.PROD and version.environment == PromptEnvironment.DEV:
                raise ValueError(
                    "Promotion rejected: Direct promotion from DEV to PROD is prohibited. "
                    "Prompt must first be promoted and validated in STAGING (or use force=True with authorization)."
                )

        # Deactivate current active version for this environment
        await session.execute(
            update(PromptVersion)
            .where(
                PromptVersion.template_id == template_id,
                PromptVersion.environment == target_environment,
                PromptVersion.is_active,
            )
            .values(is_active=False)
        )

        version.environment = target_environment
        version.is_active = True
        session.add(version)
        await session.commit()
        await session.refresh(version)

        # Invalidate cache
        await cls.invalidate_cache(template.workspace_id, template.slug, target_environment)

        logger.info(
            "prompt_version_promoted",
            template_id=str(template_id),
            version=version_number,
            environment=target_environment.value,
            forced=force,
        )

        return version

    @classmethod
    async def rollback_version(
        cls,
        session: AsyncSession,
        template_id: UUID,
        target_environment: PromptEnvironment = PromptEnvironment.PROD,
    ) -> PromptVersion:
        template = await session.get(PromptTemplate, template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Find previous active or previous version number
        versions_stmt = (
            select(PromptVersion)
            .where(
                PromptVersion.template_id == template_id,
                PromptVersion.environment == target_environment,
            )
            .order_by(PromptVersion.version_number.desc())
            .limit(2)
        )
        recent = (await session.execute(versions_stmt)).scalars().all()
        if len(recent) < 2:
            raise ValueError("No prior version available to rollback to.")

        current = recent[0]
        previous = recent[1]

        current.is_active = False
        previous.is_active = True
        session.add(current)
        session.add(previous)
        await session.commit()
        await session.refresh(previous)

        await cls.invalidate_cache(template.workspace_id, template.slug, target_environment)
        return previous
