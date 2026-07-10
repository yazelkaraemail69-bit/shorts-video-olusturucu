"""Geriye dönük import — asıl mantık director.pipeline."""

from app.services.director.pipeline import (  # noqa: F401
    get_job_critique,
    produce_from_scenario,
    refine_job,
)
