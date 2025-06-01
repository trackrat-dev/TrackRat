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
        "Hamilton": "HA",
        "Morristown": "MOR",
        "Madison": "MAD",
        "Summit": "SUM",
        "Millburn": "MIL",
        "Short Hills": "SHI",
        "Newark Airport": "EWR",
        "Elizabeth": "ELZ",
        "Linden": "LI",
        "Rahway": "RAH",
        "Metuchen": "MET",
        "Edison": "EDI",
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
        "Orange": "ORA",
        "East Orange": "EOR",
        "Brick Church": "BRC",
        "Newark Broad Street": "NBS",
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
        "Union": "UNI",

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
        "Philadelphia": "PHL",
        "Wilmington": "WIL",
        "Aberdeen": "ABE",
        "BWI Airport": "BWI",
        "Baltimore Penn Station": "BAL",
        "New Carrollton": "NCR",
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
        "Roanoke": "ROA"
    }
    
    # Name variations and aliases for fuzzy matching
    NAME_ALIASES: Dict[str, List[str]] = {
        "Trenton": ["Trenton Transit Center", "Trenton Station", "TRENT"],
        "Hamilton": ["Hamilton Station", "Hamilton NJ", "HAMIL"],
        "New York Penn Station": ["NY Penn", "Penn Station NY", "Penn Station New York", "NEW YORK", "New York", "NY PENN"],
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
    # Some frontend codes don't match what's actually in the database
    FRONTEND_TO_DB_CODE: Dict[str, str] = {
        "HA": "HL",  # Hamilton: Frontend expects "HA" but database has "HL"
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
        # Amtrak uses some station names that need normalization
        "EWR": {"code": "NP", "name": "Newark Penn Station"},  # Amtrak sometimes uses EWR for Newark Penn
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
                        logger.debug(f"Partial alias match: '{station_name}' -> '{alias}' -> '{primary_name}' ({self.STATION_CODES[primary_name]})")
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
    
    def normalize_amtrak_station(self, station_code: Optional[str], station_name: Optional[str]) -> Dict[str, Optional[str]]:
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
            logger.debug(f"Normalized Amtrak station code '{station_code}' -> '{normalized['code']}' ({normalized['name']})")
            return {"code": normalized["code"], "name": normalized["name"]}
        
        # Try name-based normalization
        if station_name and station_name in self.AMTRAK_NAME_TO_NJT:
            normalized = self.AMTRAK_NAME_TO_NJT[station_name]
            logger.debug(f"Normalized Amtrak station name '{station_name}' -> '{normalized['code']}' ({normalized['name']})")
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
        
        # Ensure we have a string
        if not isinstance(time_str, str):
            logger.warning(f"Expected string for time normalization, got {type(time_str)}: {time_str}")
            return str(time_str) if time_str is not None else None
        
        try:
            from datetime import datetime
            # Parse the time
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # Round seconds to nearest minute
            if dt.second >= 30:
                # Round up - add one minute
                from datetime import timedelta
                dt = dt.replace(second=0, microsecond=0)
                dt = dt + timedelta(minutes=1)
            else:
                # Round down
                dt = dt.replace(second=0, microsecond=0)
            
            # Return in same format
            return dt.isoformat()
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to normalize time '{time_str}': {str(e)}")
            return time_str
