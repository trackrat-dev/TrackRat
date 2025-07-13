"""
Train-related utility functions for TrackRat V2.
"""


def is_amtrak_train(train_id: str) -> bool:
    """Determine if a train ID is for an Amtrak train.

    Amtrak trains follow the pattern: A + digits (e.g., A153, A2290)

    Args:
        train_id: The train identifier

    Returns:
        True if this is an Amtrak train ID
    """
    if not train_id or len(train_id) < 2:
        return False

    return train_id.startswith("A") and train_id[1:].isdigit()


def get_train_data_source(train_id: str) -> str:
    """Get the data source for a train based on its ID.

    Args:
        train_id: The train identifier

    Returns:
        Data source: "AMTRAK" or "NJT"
    """
    return "AMTRAK" if is_amtrak_train(train_id) else "NJT"
