# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""All the steps to transform community reports."""

import pandas as pd

from graphrag.cache.pipeline_cache import PipelineCache
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config import defaults
from graphrag.config.enums import AsyncType
from graphrag.index.operations.finalize_community_reports import (
    finalize_community_reports,
)
from graphrag.index.operations.summarize_communities import (
    prepare_community_reports,
    summarize_communities,
)
from graphrag.index.operations.summarize_communities.community_reports_extractor.schemas import (
    CLAIM_DESCRIPTION,
    CLAIM_DETAILS,
    CLAIM_ID,
    CLAIM_STATUS,
    CLAIM_SUBJECT,
    CLAIM_TYPE,
    COMMUNITY_ID,
    EDGE_DEGREE,
    EDGE_DESCRIPTION,
    EDGE_DETAILS,
    EDGE_ID,
    EDGE_SOURCE,
    EDGE_TARGET,
    NODE_DEGREE,
    NODE_DESCRIPTION,
    NODE_DETAILS,
    NODE_ID,
    NODE_NAME,
)
from graphrag.index.operations.summarize_communities.prep_level_contexts import (
    prep_level_contexts,
)


async def create_community_reports(
    edges_input: pd.DataFrame,
    entities: pd.DataFrame,
    communities: pd.DataFrame,
    claims_input: pd.DataFrame | None,
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

    nodes = _prep_nodes(nodes)
    edges = _prep_edges(edges_input)

    claims = None
    if claims_input is not None:
        claims = _prep_claims(claims_input)

    max_input_length = summarization_strategy.get(
        "max_input_length", defaults.COMMUNITY_REPORT_MAX_INPUT_LENGTH
    )

    local_contexts = prepare_community_reports(
        nodes,
        edges,
        claims,
        callbacks,
        max_input_length,
    )

    level_contexts = prep_level_contexts(
        nodes,
        local_contexts,
        max_input_length,
    )

    community_reports = await summarize_communities(
        local_contexts,
        level_contexts,
        callbacks,
        cache,
        summarization_strategy,
        async_mode=async_mode,
        num_threads=num_threads,
    )

    return finalize_community_reports(community_reports, communities)


def _prep_nodes(input: pd.DataFrame) -> pd.DataFrame:
    """Prepare nodes by filtering, filling missing descriptions, and creating NODE_DETAILS."""
    # Filter rows where community is not -1
    input = input.loc[input.loc[:, COMMUNITY_ID] != -1]

    # Fill missing values in NODE_DESCRIPTION
    input.loc[:, NODE_DESCRIPTION] = input.loc[:, NODE_DESCRIPTION].fillna(
        "No Description"
    )

    # Create NODE_DETAILS column
    input.loc[:, NODE_DETAILS] = input.loc[
        :, [NODE_ID, NODE_NAME, NODE_DESCRIPTION, NODE_DEGREE]
    ].to_dict(orient="records")

    return input


def _prep_edges(input: pd.DataFrame) -> pd.DataFrame:
    # Fill missing NODE_DESCRIPTION
    input.fillna(value={NODE_DESCRIPTION: "No Description"}, inplace=True)

    # Create EDGE_DETAILS column
    input.loc[:, EDGE_DETAILS] = input.loc[
        :, [EDGE_ID, EDGE_SOURCE, EDGE_TARGET, EDGE_DESCRIPTION, EDGE_DEGREE]
    ].to_dict(orient="records")

    return input


def _prep_claims(input: pd.DataFrame) -> pd.DataFrame:
    # Fill missing NODE_DESCRIPTION
    input.fillna(value={NODE_DESCRIPTION: "No Description"}, inplace=True)

    # Create CLAIM_DETAILS column
    input.loc[:, CLAIM_DETAILS] = input.loc[
        :, [CLAIM_ID, CLAIM_SUBJECT, CLAIM_TYPE, CLAIM_STATUS, CLAIM_DESCRIPTION]
    ].to_dict(orient="records")

    return input
