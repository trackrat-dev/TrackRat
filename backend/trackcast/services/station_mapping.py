"""
Station code mapping service for TrackCast.

This module provides mappings between station names and their codes,
supporting both NJ Transit and Amtrak stations.
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class StationMapper:
    """
    Service for mapping between station names and codes.

    Provides functionality to:
    - Map station names to codes
    - Map codes to station names
    - Handle name variations and aliases
    - Validate station codes
    """

    # Keep in sync with TrackRat/Models/Stations.swift
    # Station name to code mapping
    STATION_CODES: Dict[str, str] = {
        # NJ Transit stations
        "New York Penn Station": "NY",
        "Newark Penn Station": "NP",
        "Secaucus Upper Lvl": "SE",
        "Woodbridge": "WDB",
        "Metropark": "MP",
        "New Brunswick": "NB",
        "Princeton Junction": "PJ",
        "Trenton": "TR",
        "Trenton Transit Center": "TR",
        "Hamilton": "HL",
        "Morristown": "MOR",
        "Madison": "MAD",
        "Summit": "ST",
        "Millburn": "MB",
        "Short Hills": "RT",
        "Newark Airport": "NA",
        "Elizabeth": "EZ",
        "Linden": "LI",
        "Rahway": "RH",
        "Metuchen": "MU",
        "Edison": "ED",
        "Iselin": "ISE",
        "Perth Amboy": "PAM",
        "South Amboy": "SAM",
        "Aberdeen-Matawan": "ABM",
        "Hazlet": "HAZ",
        "Red Bank": "RBK",
        "Little Silver": "LIS",
        "Monmouth Park": "MPK",
        "Long Branch": "LBR",
        "Asbury Park": "ASB",
        "Bradley Beach": "BRB",
        "Belmar": "BEL",
        "Spring Lake": "SPL",
        "Manasquan": "MAN",
        "Point Pleasant Beach": "PPB",
        "Bay Head": "BAY",
        "Montclair State University": "MSU",
        "Montclair Heights": "MCH",
        "Upper Montclair": "UMC",
        "Mountain Avenue": "MVA",
        "Orange": "OG",
        "East Orange": "EOR",
        "Brick Church": "BU",
        "Newark Broad Street": "ND",
        "Bloomfield": "BLO",
        "Watsessing": "WAT",
        "Walnut Street": "WNS",
        "Glen Ridge": "GLR",
        "Ridgewood": "RID",
        "Ho-Ho-Kus": "HHK",
        "Waldwick": "WAL",
        "Allendale": "ALL",
        "Ramsey Route 17": "RR17",
        "Ramsey Main Street": "RMS",
        "Mahwah": "MAH",
        "Suffern": "SUF",
        "Sloatsburg": "SLO",
        "Tuxedo": "TUX",
        "Harriman": "HAR",
        "Goshen": "GOS",
        "Campbell Hall": "CAM",
        "Salisbury Mills-Cornwall": "SMC",
        "New Hampton": "NHA",
        "Middletown NJ": "MTN",
        "Otisville": "OTI",
        "Port Jervis": "PJE",
        "Denville": "DEN",
        "Mount Tabor": "MTA",
        "Parsippany": "PAR",
        "Boonton": "BOO",
        "Mountain Lakes": "MLA",
        "Convent Station": "CON",
        "Chatham": "CHA",
        "New Providence": "NPR",
        "Murray Hill": "MUR",
        "Berkeley Heights": "BER",
        "Gillette": "GIL",
        "Stirling": "STI",
        "Millington": "MIL2",
        "Lyons": "LYO",
        "Basking Ridge": "BAS",
        "Bernardsville": "BER2",
        "Far Hills": "FAR",
        "Peapack": "PEA",
        "Gladstone": "GLA",
        "Annandale": "ANN",
        "Lebanon": "LEB",
        "White House": "WHI",
        "North Branch": "NBR",
        "Raritan": "RAR",
        "Somerville": "SOM",
        "Bound Brook": "BBK",
        "Dunellen": "DUN",
        "Plainfield": "PLA",
        "Netherwood": "NET",
        "Fanwood": "FAN",
        "Westfield": "WES",
        "Garwood": "GAR",
        "Cranford": "CRA",
        "Roselle Park": "ROP",
        "Union": "US",
        # Additional missing NJ Transit stations from API
        "Jersey Avenue": "JA",
        "Avenel": "AV",
        "Highland Avenue": "HI",
        "Mountain Station": "MT",
        "North Elizabeth": "NZ",
        "Bay Street": "MC",
        "Watchung Avenue": "WG",
        "Watsessing Avenue": "WT",
        # Keystone Service stations (PA)
        "Middletown": "MID",
        "Elizabethtown": "ELT",
        "Mount Joy": "MJY",
        "Lancaster": "LNC",
        "Parkesburg": "PAR",
        "Coatesville": "COT",
        "Downingtown": "DOW",
        "Exton": "EXT",
        "Paoli": "PAO",
        # Amtrak stations
        "Boston South": "BOS",
        "Boston Back Bay": "BBY",
        "Providence": "PVD",
        "New Haven": "NHV",
        "Bridgeport": "BRP",
        "Stamford": "STM",
        "New Rochelle": "NRO",
        "Yonkers": "YNY",
        "Croton-Harmon": "CRT",
        "Poughkeepsie": "POU",
        "Rhinecliff": "RHI",
        "Hudson": "HUD",
        "Albany-Rensselaer": "ALB",
        "Schenectady": "SCH",
        "Amsterdam": "AMS",
        "Utica": "UTS",
        "Rome": "ROM",
        "Syracuse": "SYR",
        "Rochester": "ROC",
        "Buffalo-Depew": "BUF",
        "Buffalo Exchange Street": "BFX",
        "Niagara Falls": "NFL",
        "Philadelphia": "PH",
        "Baltimore Station": "BL",
        "Washington Station": "WS",
        "BWI Thurgood Marshall Airport": "BA",
        "Wilmington Station": "WI",
        "New Carrollton Station": "NC",
        "Aberdeen": "ABE",
        "Washington Union": "WAS",
        "Alexandria": "AXA",
        "Fredericksburg": "FRB",
        "Richmond Staples Mill": "RSM",
        "Richmond Main Street": "RVM",
        "Petersburg": "PTB",
        "Rocky Mount": "RMT",
        "Wilson": "WIL2",
        "Selma-Smithfield": "SSM",
        "Raleigh": "RAL",
        "Cary": "CAR",
        "Southern Pines": "SPN",
        "Hamlet": "HAM2",
        "Fayetteville": "FAY",
        "Dillon": "DIL",
        "Florence": "FLO",
        "Kingstree": "KTR",
        "Charleston": "CHS",
        "Columbia": "COL",
        "Camden": "CAM2",
        "Denmark": "DEN2",
        "Savannah": "SAV",
        "Jesup": "JES",
        "Jacksonville": "JAX",
        "Palatka": "PAL",
        "DeLand": "DEL",
        "Winter Park": "WPK",
        "Orlando": "ORL",
        "Kissimmee": "KIS",
        "Lakeland": "LAK",
        "Tampa": "TPA",
        "Sebring": "SEB",
        "Okeechobee": "OKE",
        "West Palm Beach": "WPB",
        "Delray Beach": "DRB",
        "Deerfield Beach": "DFB",
        "Fort Lauderdale": "FTL",
        "Hollywood": "HOL",
        "Hallandale Beach": "HLB",
        "Aventura": "AVE",
        "Miami": "MIA",
        "Hialeah Market": "HIA",
        "Miami Airport": "MIP",
        "Toronto Union": "TOR",
        "Pittsburgh": "PIT",
        "New Orleans": "NOL",
        "Norfolk": "NFK",
        "Roanoke": "ROA",
    }

    # Name variations and aliases for fuzzy matching
    NAME_ALIASES: Dict[str, List[str]] = {
        "Trenton": ["Trenton Transit Center", "Trenton Station", "TRENT"],
        "Hamilton": ["Hamilton Station", "Hamilton NJ", "HAMIL"],
        "New York Penn Station": [
            "NY Penn",
            "Penn Station NY",
            "Penn Station New York",
            "NEW YORK",
            "New York",
            "NY PENN",
        ],
        "Newark Penn Station": ["Newark Penn", "Penn Station Newark", "NEWARK", "Newark"],
        "Secaucus Upper Lvl": ["Secaucus", "SECAU"],
        "Princeton Junction": ["Princeton Jct", "PRINC"],
        "New Brunswick": ["NEW B", "New Brunswick Station"],
        "Metropark": ["METRO", "Metro Park"],
        "Elizabeth": ["ELIZA", "Elizabeth Station"],
        "Rahway": ["RAHWA", "Rahway Station"],
        "Woodbridge": ["WOODB", "Woodbridge Station"],
        "Perth Amboy": ["PERTH", "Perth Amboy Station"],
        "South Amboy": ["SOUTH", "South Amboy Station"],
        "Aberdeen-Matawan": ["Aberdeen Matawan", "ABERD", "Aberdeen", "Matawan"],
        "Red Bank": ["RED B", "Red Bank Station"],
        "Long Branch": ["LONG", "Long Branch Station"],
        "Asbury Park": ["ASBUR", "Asbury Park Station"],
        "Point Pleasant Beach": ["Point Pleasant", "POINT", "Pt Pleasant Beach"],
        "Bay Head": ["BAY H", "Bay Head Station"],
        "Newark Broad Street": ["Newark Broad St", "Broad Street", "BROAD"],
        "Philadelphia": ["Philadelphia 30th Street", "30th Street Station", "Philly", "PHILA"],
        "Washington Union": ["Washington Union Station", "Washington DC", "Union Station", "WASHI"],
        "Baltimore Penn Station": ["Baltimore Penn", "Baltimore", "BALTI"],
        "Boston South": ["Boston South Station", "South Station", "BOSTO"],
        "Middletown NJ": ["Middletown", "MIDDL"],
        "Mount Tabor": ["Mt Tabor", "MOUNT"],
        "Mountain Lakes": ["Mtn Lakes", "MOUNT"],
        "Montclair State University": ["Montclair State", "MSU", "MONTC"],
        "Upper Montclair": ["UPPER", "Upper Montclair Station"],
        "Montclair Heights": ["MONTC", "Montclair Hts"],
        "Mountain Avenue": ["Mtn Ave", "MOUNT"],
        "East Orange": ["EAST", "E Orange"],
        "Brick Church": ["BRICK", "Brick Church Station"],
        "Roselle Park": ["ROSEL", "Roselle Park Station"],
        "Glen Ridge": ["GLEN", "Glen Ridge Station"],
        "Walnut Street": ["Walnut St", "WALNU"],
        "Ho-Ho-Kus": ["Ho Ho Kus", "Hohokus", "HO HO"],
        "Ramsey Route 17": ["Ramsey Rt 17", "Ramsey-Route 17", "RAMSE"],
        "Ramsey Main Street": ["Ramsey Main St", "Ramsey-Main Street", "RAMSE"],
        "New Hampton": ["NEW H", "New Hampton Station"],
        "Salisbury Mills-Cornwall": ["Salisbury Mills Cornwall", "Cornwall", "SALIS"],
        "Campbell Hall": ["CAMPB", "Campbell Hall Station"],
        "Port Jervis": ["PORT", "Port Jervis Station"],
        "New Providence": ["NEW P", "New Providence Station"],
        "Murray Hill": ["MURRA", "Murray Hill Station"],
        "Berkeley Heights": ["Berkeley Hts", "BERKE"],
        "Bernardsville": ["BERNA", "Bernardsville Station"],
        "Far Hills": ["FAR H", "Far Hills Station"],
        "White House": ["WHITE", "White House Station"],
        "North Branch": ["NORTH", "North Branch Station"],
        "Bound Brook": ["BOUND", "Bound Brook Station"],
        "BWI Airport": ["BWI", "BWI Airport Station"],
        "Richmond Staples Mill": ["Richmond Staples Mill Road", "Staples Mill", "RICHM"],
        "Richmond Main Street": ["Richmond Main St", "Richmond Downtown", "RICHM"],
        "Selma-Smithfield": ["Selma Smithfield", "Selma", "SELMA"],
        "Miami Airport": ["MIA Airport", "Miami International Airport", "MIAMI"],
        "Buffalo-Depew": ["Buffalo Depew", "Depew", "BUFFA"],
        "Buffalo Exchange Street": ["Buffalo Exchange St", "Exchange Street", "BUFFA"],
        "Albany-Rensselaer": ["Albany Rensselaer", "Albany", "ALBAN"],
        "N. Elizabeth": ["North Elizabeth", "N Elizabeth", "NELIZ"],
    }

    # Frontend to database code translations
    # iOS now uses actual API codes - no translation needed
    FRONTEND_TO_DB_CODE: Dict[str, str] = {
        # No longer needed - iOS station codes now match API responses
    }

    # Reverse mapping
    DB_TO_FRONTEND_CODE: Dict[str, str] = {v: k for k, v in FRONTEND_TO_DB_CODE.items()}

    # Amtrak to NJ Transit normalization mapping for consolidation
    # Maps Amtrak station codes/names to NJ Transit equivalents
    AMTRAK_TO_NJT_NORMALIZATION: Dict[str, Dict[str, str]] = {
        # Format: amtrak_code: {"code": njt_code, "name": njt_name}
        "NY": {"code": "NY", "name": "New York Penn Station"},
        "NP": {"code": "NP", "name": "Newark Penn Station"},
        "PHL": {"code": "PH", "name": "Philadelphia"},
        "WIL": {"code": "WI", "name": "Wilmington Station"},
        "BAL": {"code": "BL", "name": "Baltimore Station"},
        "BWI": {"code": "BA", "name": "BWI Thurgood Marshall Airport"},
        "WAS": {"code": "WS", "name": "Washington Station"},
        "TR": {"code": "TR", "name": "Trenton"},
        "NCR": {"code": "NC", "name": "New Carrollton Station"},
        "ALX": {"code": "AXA", "name": "Alexandria"},
        "QAN": {"code": "QAN", "name": "Quantico"},
        "FBG": {"code": "FRB", "name": "Fredericksburg"},
        "ASD": {"code": "ASD", "name": "Ashland"},
        "RVR": {"code": "RSM", "name": "Richmond"},
        # Amtrak uses some station names that need normalization
        "EWR": {
            "code": "NP",
            "name": "Newark Penn Station",
        },  # Amtrak sometimes uses EWR for Newark Penn
    }

    # Amtrak station name normalization
    AMTRAK_NAME_TO_NJT: Dict[str, Dict[str, str]] = {
        "Philadelphia 30th Street": {"code": "PH", "name": "Philadelphia"},
        "Trenton Transit Center": {"code": "TR", "name": "Trenton"},
        "Baltimore Penn": {"code": "BL", "name": "Baltimore Station"},
        "Baltimore Penn Station": {"code": "BL", "name": "Baltimore Station"},
        "Washington Union": {"code": "WS", "name": "Washington Station"},
        "Wilmington": {"code": "WI", "name": "Wilmington Station"},
        "BWI Airport": {"code": "BA", "name": "BWI Thurgood Marshall Airport"},
    }

    def __init__(self):
        """Initialize the station mapper with reverse lookups."""
        # Create reverse mapping from code to primary name
        self.CODE_TO_NAME: Dict[str, str] = {v: k for k, v in self.STATION_CODES.items()}

        # Create lowercase name to code mapping for case-insensitive lookup
        self._name_to_code_lower: Dict[str, str] = {
            name.lower(): code for name, code in self.STATION_CODES.items()
        }

        # Create lowercase alias to code mapping
        self._alias_to_code_lower: Dict[str, str] = {}
        for primary_name, aliases in self.NAME_ALIASES.items():
            if primary_name in self.STATION_CODES:
                code = self.STATION_CODES[primary_name]
                for alias in aliases:
                    self._alias_to_code_lower[alias.lower()] = code

        # Cache of all valid codes (includes both frontend and database codes)
        self._valid_codes: Set[str] = set(self.CODE_TO_NAME.keys())
        self._valid_codes.update(self.FRONTEND_TO_DB_CODE.keys())
        self._valid_codes.update(self.DB_TO_FRONTEND_CODE.keys())

    def get_code_for_name(self, station_name: Optional[str]) -> Optional[str]:
        """
        Get station code for a given station name.

        Args:
            station_name: Station name to look up

        Returns:
            Station code if found, None otherwise
        """
        if not station_name:
            return None

        station_name = station_name.strip()
        station_name_lower = station_name.lower()

        # Try exact match (case-insensitive)
        if station_name_lower in self._name_to_code_lower:
            return self._name_to_code_lower[station_name_lower]

        # Try alias match (case-insensitive)
        if station_name_lower in self._alias_to_code_lower:
            return self._alias_to_code_lower[station_name_lower]

        # Try partial match on primary names
        for name, code in self.STATION_CODES.items():
            if station_name_lower in name.lower() or name.lower() in station_name_lower:
                logger.debug(f"Partial match: '{station_name}' -> '{name}' ({code})")
                return code

        # Try partial match on aliases
        for primary_name, aliases in self.NAME_ALIASES.items():
            if primary_name in self.STATION_CODES:
                for alias in aliases:
                    if station_name_lower in alias.lower() or alias.lower() in station_name_lower:
                        logger.debug(
                            f"Partial alias match: '{station_name}' -> '{alias}' -> '{primary_name}' ({self.STATION_CODES[primary_name]})"
                        )
                        return self.STATION_CODES[primary_name]

        logger.debug(f"No match found for station name: '{station_name}'")
        return None

    def get_name_for_code(self, station_code: Optional[str]) -> Optional[str]:
        """
        Get primary station name for a given code.

        Args:
            station_code: Station code to look up

        Returns:
            Primary station name if found, None otherwise
        """
        if not station_code:
            return None

        return self.CODE_TO_NAME.get(station_code.upper())

    def is_valid_code(self, station_code: Optional[str]) -> bool:
        """
        Check if a station code is valid.

        Args:
            station_code: Station code to validate

        Returns:
            True if valid, False otherwise
        """
        if not station_code:
            return False

        return station_code.upper() in self._valid_codes

    def get_all_codes(self) -> List[str]:
        """
        Get a sorted list of all valid station codes.

        Returns:
            List of station codes
        """
        return sorted(self._valid_codes)

    def get_all_stations(self) -> Dict[str, str]:
        """
        Get all stations as a dictionary of name to code mappings.

        Returns:
            Dictionary mapping station names to codes
        """
        return self.STATION_CODES.copy()

    def translate_frontend_to_db_code(self, frontend_code: Optional[str]) -> Optional[str]:
        """
        Translate a frontend station code to its database equivalent.

        Args:
            frontend_code: Station code from frontend

        Returns:
            Database station code, or original code if no translation needed
        """
        if not frontend_code:
            return None

        # Check if this code needs translation
        if frontend_code in self.FRONTEND_TO_DB_CODE:
            return self.FRONTEND_TO_DB_CODE[frontend_code]

        # No translation needed, return as-is
        return frontend_code

    def translate_db_to_frontend_code(self, db_code: Optional[str]) -> Optional[str]:
        """
        Translate a database station code to its frontend equivalent.

        Args:
            db_code: Station code from database

        Returns:
            Frontend station code, or original code if no translation needed
        """
        if not db_code:
            return None

        # Check if this code needs translation
        if db_code in self.DB_TO_FRONTEND_CODE:
            return self.DB_TO_FRONTEND_CODE[db_code]

        # No translation needed, return as-is
        return db_code

    def normalize_amtrak_station(
        self, station_code: Optional[str], station_name: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """
        Normalize Amtrak station code and name to NJ Transit equivalents for consolidation.

        Args:
            station_code: Amtrak station code
            station_name: Amtrak station name

        Returns:
            Dictionary with normalized 'code' and 'name' keys, or originals if no mapping exists
        """
        # Try code-based normalization first
        if station_code and station_code.upper() in self.AMTRAK_TO_NJT_NORMALIZATION:
            normalized = self.AMTRAK_TO_NJT_NORMALIZATION[station_code.upper()]
            logger.debug(
                f"Normalized Amtrak station code '{station_code}' -> '{normalized['code']}' ({normalized['name']})"
            )
            return {"code": normalized["code"], "name": normalized["name"]}

        # Try name-based normalization
        if station_name and station_name in self.AMTRAK_NAME_TO_NJT:
            normalized = self.AMTRAK_NAME_TO_NJT[station_name]
            logger.debug(
                f"Normalized Amtrak station name '{station_name}' -> '{normalized['code']}' ({normalized['name']})"
            )
            return {"code": normalized["code"], "name": normalized["name"]}

        # No normalization available, return originals
        return {"code": station_code, "name": station_name}

    def normalize_time_to_nearest_minute(self, time_str: Optional[str]) -> Optional[str]:
        """
        Normalize time string to nearest minute for better consolidation matching.

        Args:
            time_str: Time string in ISO format (e.g., "2025-06-01T09:04:30")

        Returns:
            Normalized time string with seconds rounded to nearest minute
        """
        if not time_str:
            return None

        from datetime import datetime, timedelta

        # Handle different input types
        if isinstance(time_str, datetime):
            # Already a datetime object, just normalize it
            dt = time_str
        elif isinstance(time_str, str):
            # Parse string to datetime
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse time string: {time_str}")
                return time_str
        else:
            # Unexpected type, log and return as string
            logger.debug(
                f"Converting {type(time_str)} to string for time normalization: {time_str}"
            )
            return str(time_str) if time_str is not None else None

        try:
            # Round seconds to nearest minute
            if dt.second >= 30:
                # Round up - add one minute
                dt = dt.replace(second=0, microsecond=0)
                dt = dt + timedelta(minutes=1)
            else:
                # Round down
                dt = dt.replace(second=0, microsecond=0)

            # Return in same format
            return dt.isoformat()

        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Failed to normalize time '{time_str}': {str(e)}")
            return str(time_str) if time_str is not None else None

    def validate_sync_with_ios(self, ios_station_codes: Dict[str, str]) -> Dict[str, any]:
        """
        Validate that backend station codes are in sync with iOS app.

        Args:
            ios_station_codes: Station codes dictionary from iOS app

        Returns:
            Dictionary with validation results and any discrepancies
        """
        validation_result = {
            "in_sync": True,
            "backend_only": [],
            "ios_only": [],
            "code_mismatches": [],
            "total_backend": len(self.STATION_CODES),
            "total_ios": len(ios_station_codes),
        }

        # Find stations only in backend
        for name, code in self.STATION_CODES.items():
            if name not in ios_station_codes:
                validation_result["backend_only"].append({"name": name, "code": code})

        # Find stations only in iOS
        for name, code in ios_station_codes.items():
            if name not in self.STATION_CODES:
                validation_result["ios_only"].append({"name": name, "code": code})

        # Find code mismatches
        for name in set(self.STATION_CODES.keys()) & set(ios_station_codes.keys()):
            backend_code = self.STATION_CODES[name]
            ios_code = ios_station_codes[name]
            if backend_code != ios_code:
                validation_result["code_mismatches"].append(
                    {"name": name, "backend_code": backend_code, "ios_code": ios_code}
                )

        # Determine if in sync
        if (
            validation_result["backend_only"]
            or validation_result["ios_only"]
            or validation_result["code_mismatches"]
        ):
            validation_result["in_sync"] = False

        return validation_result

    def log_validation_results(self, validation_result: Dict[str, any]) -> None:
        """Log validation results in a readable format."""
        if validation_result["in_sync"]:
            logger.info("✅ Backend and iOS station codes are in sync!")
            logger.info(f"Total stations: {validation_result['total_backend']}")
        else:
            logger.warning("❌ Backend and iOS station codes are NOT in sync!")

            if validation_result["backend_only"]:
                logger.warning(
                    f"Stations only in backend ({len(validation_result['backend_only'])}):"
                )
                for station in validation_result["backend_only"][:5]:  # Limit output
                    logger.warning(f"  - {station['name']}: {station['code']}")
                if len(validation_result["backend_only"]) > 5:
                    logger.warning(f"  ... and {len(validation_result['backend_only']) - 5} more")

            if validation_result["ios_only"]:
                logger.warning(f"Stations only in iOS ({len(validation_result['ios_only'])}):")
                for station in validation_result["ios_only"][:5]:  # Limit output
                    logger.warning(f"  - {station['name']}: {station['code']}")
                if len(validation_result["ios_only"]) > 5:
                    logger.warning(f"  ... and {len(validation_result['ios_only']) - 5} more")

            if validation_result["code_mismatches"]:
                logger.warning(f"Code mismatches ({len(validation_result['code_mismatches'])}):")
                for mismatch in validation_result["code_mismatches"]:
                    logger.warning(
                        f"  - {mismatch['name']}: backend='{mismatch['backend_code']}' vs ios='{mismatch['ios_code']}'"
                    )

    @classmethod
    def create_sync_validation_cli_command(cls):
        """
        Create a CLI command function for validating sync with iOS.
        This would be added to the CLI module.
        """

        def validate_station_sync():
            """CLI command to validate station code sync between backend and iOS."""
            # This would need to read the iOS Stations.swift file
            # For now, we'll just show how to use the validation
            mapper = cls()

            # Example of how this would work with actual iOS data
            logger.info("To validate sync, you would:")
            logger.info("1. Extract station codes from ios/TrackRat/Models/Stations.swift")
            logger.info("2. Pass them to mapper.validate_sync_with_ios(ios_codes)")
            logger.info("3. Call mapper.log_validation_results(result)")

            return True

        return validate_station_sync
