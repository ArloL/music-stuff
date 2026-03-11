def hex_id_to_beatunes_id(hex_id: str) -> int:
    """Convert an Apple Music hex persistent ID to a beaTunes ID."""
    value = int(hex_id, 16)
    if value >= (1 << 63):
        value -= (1 << 64)
    return value ^ (-(1 << 63))


def beatunes_id_to_hex_id(beatunes_id: int) -> str:
    """Convert a beaTunes ID to an Apple Music hex persistent ID."""
    value = beatunes_id ^ (-(1 << 63))
    if value < 0:
        value += (1 << 64)
    return format(value, "016X")
