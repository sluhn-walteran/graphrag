# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""All the steps to transform community reports."""

import logging
from uuid import uuid4

import pandas as pd

from graphrag.cache.pipeline_cache import PipelineCache
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config import defaults
from graphrag.config.enums import AsyncType
from graphrag.index.operations.summarize_communities import (
    restore_community_hierarchy,
    summarize_communities,
)
from graphrag.index.operations.summarize_communities.community_reports_extractor.utils import (
    get_levels,
)
from graphrag.index.operations.summarize_communities_text.context_builder import (
    prep_community_report_context,
    prep_local_context,
)
from graphrag.index.operations.summarize_communities_text.prompts import (
    COMMUNITY_REPORT_PROMPT,
)

log = logging.getLogger(__name__)


async def create_final_community_reports_text(
    entities: pd.DataFrame,
    communities: pd.DataFrame,
    text_units: pd.DataFrame,
    callbacks: WorkflowCallbacks,
    cache: PipelineCache,
    summarization_strategy: dict,
    async_mode: AsyncType = AsyncType.AsyncIO,
    num_threads: int = 4,
) -> pd.DataFrame:
    """All the steps to transform community reports."""
    community_join = communities.explode("entity_ids").loc[
        :, ["community", "level", "entity_ids"]
    ]
    nodes = entities.merge(
        community_join, left_on="id", right_on="entity_ids", how="left"
    )
    nodes = nodes.loc[nodes.loc[:, "community"] != -1]

    max_input_length = summarization_strategy.get("max_input_length", 16_000)

    # TEMP: forcing override of the prompt until we can put it into config
    summarization_strategy["extraction_prompt"] = COMMUNITY_REPORT_PROMPT
    # build initial local context for all communities
    local_contexts = prep_local_context(
        communities, text_units, nodes, max_input_length
    )

    community_hierarchy = restore_community_hierarchy(nodes)
    levels = get_levels(nodes)

    level_contexts = []
    for level in levels:
        level_context = prep_community_report_context(
            local_context_df=local_contexts,
            community_hierarchy_df=community_hierarchy,
            level=level,
            max_tokens=summarization_strategy.get(
                "max_input_tokens", defaults.COMMUNITY_REPORT_MAX_INPUT_LENGTH
            ),
        )
        level_contexts.append(level_context)

    community_reports = await summarize_communities(
        local_contexts,
        level_contexts,
        callbacks,
        cache,
        summarization_strategy,
        async_mode=async_mode,
        num_threads=num_threads,
    )

    community_reports["community"] = community_reports["community"].astype(int)
    community_reports["human_readable_id"] = community_reports["community"]
    community_reports["id"] = [uuid4().hex for _ in range(len(community_reports))]

    # Merge with communities to add size and period
    merged = community_reports.merge(
        communities.loc[:, ["community", "parent", "size", "period"]],
        on="community",
        how="left",
        copy=False,
    )
    return merged.loc[
        :,
        [
            "id",
            "human_readable_id",
            "community",
            "parent",
            "level",
            "title",
            "summary",
            "full_content",
            "rank",
            "rank_explanation",
            "findings",
            "full_content_json",
            "period",
            "size",
        ],
    ]
