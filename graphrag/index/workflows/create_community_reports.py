# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging
import pandas as pd

log = logging.getLogger(__name__)

import graphrag.data_model.schemas as schemas
from graphrag.cache.pipeline_cache import PipelineCache
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config.defaults import graphrag_config_defaults
from graphrag.config.enums import AsyncType
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.index.operations.finalize_community_reports import (
    finalize_community_reports,
)
from graphrag.index.operations.summarize_communities.explode_communities import (
    explode_communities,
)
from graphrag.index.operations.summarize_communities.graph_context.context_builder import (
    build_level_context,
    build_local_context,
)
from graphrag.index.operations.summarize_communities.summarize_communities import (
    summarize_communities,
)
from graphrag.index.typing.context import PipelineRunContext
from graphrag.index.typing.workflow import WorkflowFunctionOutput
from graphrag.utils.storage import (
    load_table_from_storage,
    storage_has_table,
    write_table_to_storage,
)


async def run_workflow(
    config: GraphRagConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """All the steps to transform community reports."""
    edges = await load_table_from_storage("relationships", context.storage)
    entities = await load_table_from_storage("entities", context.storage)
    communities = await load_table_from_storage("communities", context.storage)
    claims = None
    if config.extract_claims.enabled and await storage_has_table(
        "covariates", context.storage
    ):
        claims = await load_table_from_storage("covariates", context.storage)

    community_reports_llm_settings = config.get_language_model_config(
        config.community_reports.model_id
    )
    async_mode = community_reports_llm_settings.async_mode
    num_threads = community_reports_llm_settings.concurrent_requests
    summarization_strategy = config.community_reports.resolved_strategy(
        config.root_dir, community_reports_llm_settings
    )

    output = await create_community_reports(
        edges_input=edges,
        entities=entities,
        communities=communities,
        claims_input=claims,
        callbacks=context.callbacks,
        cache=context.cache,
        summarization_strategy=summarization_strategy,
        async_mode=async_mode,
        num_threads=num_threads,
    )

    await write_table_to_storage(output, "community_reports", context.storage)

    return WorkflowFunctionOutput(result=output)


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
    max_communities_to_process: int | None = 5,  # Added parameter to limit communities
) -> pd.DataFrame:
    """All the steps to transform community reports."""
    # Filter communities if max_communities_to_process is set
    if max_communities_to_process is not None and len(communities) > max_communities_to_process:
        # Assuming 'log' is available (e.g., import logging; log = logging.getLogger(__name__))
        # And 'pd' for pandas (e.g., import pandas as pd)
        log.info(f"Limiting community report generation to the first {max_communities_to_process} communities out of {len(communities)}.")
        # For simplicity, taking the head. If a 'size' column exists and is relevant for prioritization,
        # consider: communities_df_subset = communities.nlargest(max_communities_to_process, "size").copy()
        communities_df_subset = communities.head(max_communities_to_process).copy()
    else:
        communities_df_subset = communities.copy()

    if communities_df_subset.empty:
        log.warning("No communities to process after filtering. Returning empty DataFrame for reports.")
        return pd.DataFrame() # Consider returning with a specific schema if known

    # Explode only the subset of communities
    nodes = explode_communities(communities_df_subset, entities)

    if nodes.empty:
        log.warning(f"No nodes found after exploding {len(communities_df_subset)} selected communities. Returning empty DataFrame for reports.")
        return pd.DataFrame()

    nodes = _prep_nodes(nodes)
    edges = _prep_edges(edges_input)

    claims = None
    if claims_input is not None:
        claims = _prep_claims(claims_input)

    summarization_strategy["extraction_prompt"] = summarization_strategy["graph_prompt"]

    max_input_length = summarization_strategy.get(
        "max_input_length", graphrag_config_defaults.community_reports.max_input_length
    )

    local_contexts = build_local_context(
        nodes,
        edges,
        claims,
        callbacks,
        max_input_length,
    )

    community_reports = await summarize_communities(
        nodes,  # Already based on filtered communities
        communities_df_subset,  # Pass the filtered communities DataFrame
        local_contexts, # local_contexts are built from the filtered 'nodes'
        build_level_context,
        callbacks,
        cache,
        summarization_strategy,
        max_input_length=max_input_length,
        async_mode=async_mode,
        num_threads=num_threads,
    )

    return finalize_community_reports(community_reports, communities_df_subset)  # Use filtered communities here as well


def _prep_nodes(input: pd.DataFrame) -> pd.DataFrame:
    """Prepare nodes by filtering, filling missing descriptions, and creating NODE_DETAILS."""
    # Fill missing values in DESCRIPTION
    input.loc[:, schemas.DESCRIPTION] = input.loc[:, schemas.DESCRIPTION].fillna(
        "No Description"
    )

    # Create NODE_DETAILS column
    input.loc[:, schemas.NODE_DETAILS] = input.loc[
        :,
        [
            schemas.SHORT_ID,
            schemas.TITLE,
            schemas.DESCRIPTION,
            schemas.NODE_DEGREE,
        ],
    ].to_dict(orient="records")

    return input


def _prep_edges(input: pd.DataFrame) -> pd.DataFrame:
    # Fill missing DESCRIPTION
    input.fillna(value={schemas.DESCRIPTION: "No Description"}, inplace=True)

    # Create EDGE_DETAILS column
    input.loc[:, schemas.EDGE_DETAILS] = input.loc[
        :,
        [
            schemas.SHORT_ID,
            schemas.EDGE_SOURCE,
            schemas.EDGE_TARGET,
            schemas.DESCRIPTION,
            schemas.EDGE_DEGREE,
        ],
    ].to_dict(orient="records")

    return input


def _prep_claims(input: pd.DataFrame) -> pd.DataFrame:
    # Fill missing DESCRIPTION
    input.fillna(value={schemas.DESCRIPTION: "No Description"}, inplace=True)

    # Create CLAIM_DETAILS column
    input.loc[:, schemas.CLAIM_DETAILS] = input.loc[
        :,
        [
            schemas.SHORT_ID,
            schemas.CLAIM_SUBJECT,
            schemas.TYPE,
            schemas.CLAIM_STATUS,
            schemas.DESCRIPTION,
        ],
    ].to_dict(orient="records")

    return input
