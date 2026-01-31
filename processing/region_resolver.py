REGION_MAP = {
    "manchester": "UK_NORTH_WEST",
    "leeds": "UK_YORKSHIRE"
}

def resolve_region(location: str):
    if not location:
        return None
    return REGION_MAP.get(location.lower())
