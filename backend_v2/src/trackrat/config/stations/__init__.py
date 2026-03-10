"""Station configuration for TrackRat V2.

This package splits station data into per-system modules for maintainability.
All public symbols are re-exported here so existing imports continue to work:
    from trackrat.config.stations import STATION_NAMES, get_station_name, ...
"""

__all__ = [
    # NJT
    "NJT_GTFS_STOP_TO_INTERNAL_MAP",
    "NJT_STATION_NAMES",
    "DISCOVERY_STATIONS",
    # Amtrak
    "AMTRAK_STATION_NAMES",
    "AMTRAK_TO_INTERNAL_STATION_MAP",
    "INTERNAL_TO_AMTRAK_STATION_MAP",
    "map_amtrak_station_code",
    "map_internal_to_amtrak_code",
    # PATH
    "INTERNAL_TO_PATH_TRANSITER_MAP",
    "PATH_DISCOVERY_STATIONS",
    "PATH_GTFS_NAME_TO_INTERNAL_MAP",
    "PATH_RIDEPATH_API_TO_INTERNAL_MAP",
    "PATH_ROUTE_STOPS",
    "PATH_ROUTES",
    "PATH_STATION_NAMES",
    "PATH_TRANSITER_TO_INTERNAL_MAP",
    "get_path_route_and_stops",
    "get_path_route_info",
    "get_path_route_stops",
    "get_path_stops_by_origin_destination",
    "map_internal_to_path_station",
    "map_path_station_code",
    # PATCO
    "INTERNAL_TO_PATCO_GTFS_STOP_MAP",
    "PATCO_GTFS_FEED_URL",
    "PATCO_GTFS_STOP_TO_INTERNAL_MAP",
    "PATCO_ROUTE_STOPS",
    "PATCO_ROUTES",
    "PATCO_STATION_NAMES",
    "PATCO_TERMINUS_STATIONS",
    "get_patco_route_info",
    "get_patco_route_stops",
    "map_patco_gtfs_stop",
    # LIRR
    "INTERNAL_TO_LIRR_GTFS_STOP_MAP",
    "LIRR_DISCOVERY_STATIONS",
    "LIRR_ALERTS_FEED_URL",
    "LIRR_GTFS_RT_FEED_URL",
    "LIRR_GTFS_STOP_TO_INTERNAL_MAP",
    "LIRR_ROUTES",
    "LIRR_STATION_NAMES",
    "get_lirr_route_info",
    "map_lirr_gtfs_stop",
    # Subway
    "INTERNAL_TO_SUBWAY_GTFS_STOP_MAP",
    "SUBWAY_STATION_COMPLEXES",
    "SUBWAY_DISCOVERY_STATIONS",
    "SUBWAY_ALERTS_FEED_URL",
    "SUBWAY_GTFS_RT_FEED_URLS",
    "SUBWAY_GTFS_STATIC_URL",
    "SUBWAY_GTFS_STOP_TO_INTERNAL_MAP",
    "SUBWAY_ROUTES",
    "SUBWAY_STATION_COORDINATES",
    "SUBWAY_STATION_NAMES",
    "get_subway_route_info",
    "map_subway_gtfs_stop",
    # MNR
    "INTERNAL_TO_MNR_GTFS_STOP_MAP",
    "MNR_DISCOVERY_STATIONS",
    "MNR_ALERTS_FEED_URL",
    "MNR_GTFS_RT_FEED_URL",
    "MNR_GTFS_STOP_TO_INTERNAL_MAP",
    "MNR_ROUTES",
    "MNR_STATION_NAMES",
    "get_mnr_route_info",
    "map_mnr_gtfs_stop",
    # Common
    "STATION_COORDINATES",
    "STATION_EQUIVALENCE_GROUPS",
    "STATION_EQUIVALENTS",
    "STATION_NAMES",
    "_build_name_to_code_map",
    "_normalize_station_name",
    "canonical_station_code",
    "expand_station_codes",
    "get_all_stations",
    "get_station_code_by_name",
    "get_station_coordinates",
    "get_station_name",
    "map_gtfs_stop_to_station_code",
]

# NJT
# Amtrak
from trackrat.config.stations.amtrak import (
    AMTRAK_STATION_NAMES,
    AMTRAK_TO_INTERNAL_STATION_MAP,
    INTERNAL_TO_AMTRAK_STATION_MAP,
    map_amtrak_station_code,
    map_internal_to_amtrak_code,
)

# Common (unified data + shared functions)
from trackrat.config.stations.common import (
    STATION_COORDINATES,
    STATION_EQUIVALENCE_GROUPS,
    STATION_EQUIVALENTS,
    STATION_NAMES,
    _build_name_to_code_map,
    _normalize_station_name,
    canonical_station_code,
    expand_station_codes,
    get_all_stations,
    get_station_code_by_name,
    get_station_coordinates,
    get_station_name,
    map_gtfs_stop_to_station_code,
)

# LIRR
from trackrat.config.stations.lirr import (
    INTERNAL_TO_LIRR_GTFS_STOP_MAP,
    LIRR_ALERTS_FEED_URL,
    LIRR_DISCOVERY_STATIONS,
    LIRR_GTFS_RT_FEED_URL,
    LIRR_GTFS_STOP_TO_INTERNAL_MAP,
    LIRR_ROUTES,
    LIRR_STATION_NAMES,
    get_lirr_route_info,
    map_lirr_gtfs_stop,
)

# MNR
from trackrat.config.stations.mnr import (
    INTERNAL_TO_MNR_GTFS_STOP_MAP,
    MNR_ALERTS_FEED_URL,
    MNR_DISCOVERY_STATIONS,
    MNR_GTFS_RT_FEED_URL,
    MNR_GTFS_STOP_TO_INTERNAL_MAP,
    MNR_ROUTES,
    MNR_STATION_NAMES,
    get_mnr_route_info,
    map_mnr_gtfs_stop,
)
from trackrat.config.stations.njt import (
    DISCOVERY_STATIONS,
    NJT_GTFS_STOP_TO_INTERNAL_MAP,
    NJT_STATION_NAMES,
)

# PATCO
from trackrat.config.stations.patco import (
    INTERNAL_TO_PATCO_GTFS_STOP_MAP,
    PATCO_GTFS_FEED_URL,
    PATCO_GTFS_STOP_TO_INTERNAL_MAP,
    PATCO_ROUTE_STOPS,
    PATCO_ROUTES,
    PATCO_STATION_NAMES,
    PATCO_TERMINUS_STATIONS,
    get_patco_route_info,
    get_patco_route_stops,
    map_patco_gtfs_stop,
)

# PATH
from trackrat.config.stations.path import (
    INTERNAL_TO_PATH_TRANSITER_MAP,
    PATH_DISCOVERY_STATIONS,
    PATH_GTFS_NAME_TO_INTERNAL_MAP,
    PATH_RIDEPATH_API_TO_INTERNAL_MAP,
    PATH_ROUTE_STOPS,
    PATH_ROUTES,
    PATH_STATION_NAMES,
    PATH_TRANSITER_TO_INTERNAL_MAP,
    get_path_route_and_stops,
    get_path_route_info,
    get_path_route_stops,
    get_path_stops_by_origin_destination,
    map_internal_to_path_station,
    map_path_station_code,
)

# Subway
from trackrat.config.stations.subway import (
    INTERNAL_TO_SUBWAY_GTFS_STOP_MAP,
    SUBWAY_ALERTS_FEED_URL,
    SUBWAY_DISCOVERY_STATIONS,
    SUBWAY_GTFS_RT_FEED_URLS,
    SUBWAY_GTFS_STATIC_URL,
    SUBWAY_GTFS_STOP_TO_INTERNAL_MAP,
    SUBWAY_ROUTES,
    SUBWAY_STATION_COMPLEXES,
    SUBWAY_STATION_COORDINATES,
    SUBWAY_STATION_NAMES,
    get_subway_route_info,
    map_subway_gtfs_stop,
)
