"""
Regression test for issue #919: Train detail fallback queries must eager-load
progress_snapshots to avoid raise_on_sql errors.

The get_train_details endpoint has fallback re-query paths (JIT timeout, flush
failure) that previously only loaded TrainJourney.stops, causing crashes when
journey.progress_snapshots was accessed downstream. This test verifies that
every query in get_train_details that loads stops also loads progress_snapshots.
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


def test_all_fallback_queries_include_progress_snapshots():
    """Every .options(selectinload(TrainJourney.stops)) call in get_train_details
    must also include selectinload(TrainJourney.progress_snapshots).

    This prevents raise_on_sql errors when the response builder accesses
    journey.progress_snapshots after a fallback re-query path.
    """
    source = inspect.getsource(trains_module)
    # Dedent so AST parsing works regardless of module-level indentation
    source = textwrap.dedent(source)

    groups = _extract_selectinload_groups(source, "get_train_details")

    assert len(groups) >= 3, (
        f"Expected at least 3 .options() calls in get_train_details "
        f"(pre-fetch, timeout fallback, flush fallback), found {len(groups)}. "
        f"If queries were refactored, update this test."
    )

    for i, group in enumerate(groups):
        if "stops" in group:
            assert "progress_snapshots" in group, (
                f".options() call #{i + 1} in get_train_details loads "
                f"'stops' but is missing 'progress_snapshots'. "
                f"Found: {group}. "
                f"All fallback queries must eager-load progress_snapshots "
                f"to avoid raise_on_sql errors (see issue #919)."
            )


def test_selectinload_group_extraction_works():
    """Verify the AST extraction helper works correctly on the actual source."""
    source = inspect.getsource(trains_module)
    source = textwrap.dedent(source)

    groups = _extract_selectinload_groups(source, "get_train_details")

    # Every group should have at least 'stops' since that's always loaded
    for group in groups:
        assert "stops" in group, (
            f"Found a .options() group without 'stops': {group}. "
            f"This is unexpected — all queries in get_train_details should load stops."
        )
