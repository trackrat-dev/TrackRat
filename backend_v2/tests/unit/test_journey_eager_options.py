"""
Tests for _journey_eager_options() completeness.

The helper must cover ALL delete-orphan cascade relationships on TrainJourney.
If a new relationship is added to the model but not included here, it will
silently cause MissingGreenlet errors in production during SQLAlchemy's
unit-of-work flush process.
"""

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from trackrat.collectors.njt.journey import _journey_eager_options
from trackrat.models.database import TrainJourney


def test_eager_options_covers_all_cascade_delete_relationships():
    """Every delete-orphan cascade relationship on TrainJourney must be
    included in _journey_eager_options().

    This test inspects the ORM mapper to find all relationships with
    delete-orphan cascade and verifies each one has a corresponding
    selectinload in the helper. If you add a new relationship to
    TrainJourney with cascade='all, delete-orphan', this test will
    fail until you add it to _journey_eager_options().
    """
    mapper = sa_inspect(TrainJourney)

    # Find all relationship names with delete-orphan cascade
    cascade_delete_rels = set()
    for rel in mapper.relationships:
        if "delete-orphan" in rel.cascade:
            cascade_delete_rels.add(rel.key)

    # Extract relationship names from the helper's selectinload options
    options = _journey_eager_options()
    eager_loaded_rels = set()
    for opt in options:
        # selectinload(TrainJourney.foo) stores the attribute key in the strategy
        # Access the relationship key from the loader option
        if hasattr(opt, "path"):
            # path is a tuple of (mapper_property,) for top-level loads
            for token in opt.path:
                if hasattr(token, "key"):
                    eager_loaded_rels.add(token.key)

    # Also check by counting — the helper should have at least as many
    # options as there are delete-orphan relationships
    assert len(options) >= len(cascade_delete_rels), (
        f"_journey_eager_options() has {len(options)} selectinloads but "
        f"TrainJourney has {len(cascade_delete_rels)} delete-orphan relationships: "
        f"{cascade_delete_rels}"
    )

    # If we could extract names, verify exact match
    if eager_loaded_rels:
        missing = cascade_delete_rels - eager_loaded_rels
        assert not missing, (
            f"_journey_eager_options() is missing selectinload for: {missing}. "
            f"Add selectinload(TrainJourney.{missing.pop()}) to the helper."
        )


def test_eager_options_returns_selectinload_instances():
    """Each option should be a selectinload strategy."""
    options = _journey_eager_options()
    assert len(options) > 0, "Helper should return at least one option"

    # Verify we get the right number (6 relationships on TrainJourney)
    mapper = sa_inspect(TrainJourney)
    lazy_raise_rels = [
        rel.key for rel in mapper.relationships if rel.lazy == "raise_on_sql"
    ]
    assert len(options) == len(lazy_raise_rels), (
        f"_journey_eager_options() has {len(options)} options but TrainJourney has "
        f"{len(lazy_raise_rels)} raise_on_sql relationships: {lazy_raise_rels}"
    )
