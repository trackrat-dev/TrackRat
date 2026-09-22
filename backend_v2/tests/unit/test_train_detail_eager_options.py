"""
Regression test for issue #919: Train detail journey loads must eager-load
progress_snapshots to avoid raise_on_sql errors.

The get_train_details endpoint has fallback re-query paths (JIT timeout, flush
failure) that previously only loaded TrainJourney.stops, causing crashes when
journey.progress_snapshots was accessed downstream.

Those three queries were identical apart from that bug, and #1752 needed a
fourth behaviour from all of them (an adjacent-date fallback), so they are now
one helper — ``_load_journey_for_date``. That makes #919's invariant structural
rather than repeated: there is a single place to get the eager loads right, and
no fourth path can be added that forgets them. These tests check both halves of
that: the helper loads both relationships, and the endpoint still routes every
journey load through it instead of reintroducing an inline query.
"""

import ast
import inspect
import textwrap

from trackrat.api import trains as trains_module


def _extract_selectinload_groups(source: str, function_name: str) -> list[set[str]]:
    """Parse source AST and find groups of selectinload calls within .options()
    calls inside the given function.

    Returns a list of sets, where each set contains the attribute names passed
    to selectinload() in a single .options() call.

    Example: .options(selectinload(TrainJourney.stops), selectinload(TrainJourney.progress_snapshots))
    -> {"stops", "progress_snapshots"}
    """
    tree = ast.parse(source)

    groups: list[set[str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != function_name:
            continue

        # Walk this function's AST looking for .options(...) calls
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            # Check if this is a .options() call
            if not isinstance(child.func, ast.Attribute):
                continue
            if child.func.attr != "options":
                continue

            # Extract selectinload attribute names from this .options() call
            attrs: set[str] = set()
            for arg in child.args:
                if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                    if arg.func.id == "selectinload" and arg.args:
                        if isinstance(arg.args[0], ast.Attribute):
                            attrs.add(arg.args[0].attr)
            if attrs:
                groups.append(attrs)

    return groups


def _module_source() -> str:
    # Dedent so AST parsing works regardless of module-level indentation
    return textwrap.dedent(inspect.getsource(trains_module))


def test_journey_loader_eager_loads_progress_snapshots():
    """The one place that loads a journey for the detail endpoint must load both.

    This is #919's invariant. It used to be repeated across three queries, with
    the fallback paths being exactly the ones that got it wrong; it now lives in
    a single helper, so this asserts it there.
    """
    groups = _extract_selectinload_groups(_module_source(), "_load_journey_for_date")

    assert groups, (
        "_load_journey_for_date has no .options(selectinload(...)) call, so the "
        "journey it returns lazy-loads its relationships — which raises "
        "MissingGreenlet under the async session (see issue #919)"
    )

    for i, group in enumerate(groups):
        if "stops" in group:
            assert "progress_snapshots" in group, (
                f".options() call #{i + 1} in _load_journey_for_date loads "
                f"'stops' but is missing 'progress_snapshots'. Found: {group}. "
                f"The response builder accesses progress_snapshots downstream "
                f"(see issue #919)."
            )


def test_train_details_does_not_load_journeys_inline():
    """No path may go around the helper and reintroduce the #919 bug.

    An inline query here is how the original defect happened: three near-copies
    of one lookup, and the two least-exercised ones missing an eager load. The
    endpoint should have no journey-loading .options() of its own.
    """
    groups = _extract_selectinload_groups(_module_source(), "get_train_details")

    assert not [g for g in groups if "stops" in g], (
        f"get_train_details loads a journey inline ({groups}) instead of "
        "through _load_journey_for_date. Either route it through the helper, "
        "or eager-load both stops and progress_snapshots here too."
    )


def test_selectinload_group_extraction_works():
    """Verify the AST extraction helper works correctly on the actual source."""
    groups = _extract_selectinload_groups(_module_source(), "_load_journey_for_date")

    # Every group should have at least 'stops' since that's always loaded
    for group in groups:
        assert "stops" in group, (
            f"Found a .options() group without 'stops': {group}. "
            f"This is unexpected — the journey loader should always load stops."
        )
