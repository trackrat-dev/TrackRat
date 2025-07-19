#!/usr/bin/env python3
"""
Migrate historical train data from PostgreSQL dump to SQLite backend_v2 database.

This script can be run multiple times safely - it will skip already imported data.
Usage: python scripts/migrate_historical_data.py [--dump-file path/to/dump.sql] [--db-file path/to/trackrat_v2.db]
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add the src directory to the path so we can import trackrat modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class HistoricalDataMigrator:
    def __init__(self, dump_file: Path, db_file: Path):
        self.dump_file = dump_file
        self.db_file = db_file
        self.conn = None
        self.trains_data = []
        self.train_stops_data = []
        self.stats = {
            "trains_found": 0,
            "journeys_created": 0,
            "stops_created": 0,
            "errors": 0,
            "skipped_duplicates": 0,
        }

    def connect(self):
        """Connect to the SQLite database."""
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite3.Row
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def parse_postgres_dump(self):
        """Parse the PostgreSQL dump file to extract train and stop data."""
        print(f"Parsing dump file: {self.dump_file}")
        
        with open(self.dump_file, "r", encoding="utf-8") as f:
            current_table = None
            in_copy = False
            line_count = 0
            
            for line in f:
                line_count += 1
                if line_count % 10000 == 0:
                    print(f"  Processed {line_count:,} lines...")
                
                # Detect COPY statements
                if line.startswith("COPY public.trains "):
                    current_table = "trains"
                    in_copy = True
                    continue
                elif line.startswith("COPY public.train_stops "):
                    current_table = "train_stops"
                    in_copy = True
                    continue
                
                # End of COPY data
                if line.strip() == "\\." and in_copy:
                    in_copy = False
                    current_table = None
                    continue
                
                # Parse data rows
                if in_copy and current_table == "trains":
                    self._parse_train_row(line.strip())
                elif in_copy and current_table == "train_stops":
                    self._parse_train_stop_row(line.strip())
        
        print(f"Parsing complete. Found {len(self.trains_data):,} trains and {len(self.train_stops_data):,} stops")

    def _parse_train_row(self, line: str):
        """Parse a single train row from the COPY data."""
        if not line:
            return
            
        parts = line.split("\t")
        if len(parts) < 19:  # Expected number of columns
            return
        
        try:
            train = {
                "id": int(parts[0]),
                "train_id": parts[1],
                "line": parts[2],
                "line_code": parts[3] if parts[3] != "\\N" else None,
                "destination": parts[4],
                "departure_time": self._parse_timestamp(parts[5]),
                "track": parts[6] if parts[6] != "\\N" else None,
                "status": parts[7] if parts[7] != "\\N" else None,
                "track_assigned_at": self._parse_timestamp(parts[8]) if parts[8] != "\\N" else None,
                "delay_minutes": int(parts[10]) if parts[10] != "\\N" else 0,
                "origin_station_code": parts[16] if parts[16] != "\\N" else "NY",
                "data_source": parts[18] if parts[18] != "\\N" else "njtransit",
            }
            self.trains_data.append(train)
            self.stats["trains_found"] += 1
        except (ValueError, IndexError) as e:
            self.stats["errors"] += 1

    def _parse_train_stop_row(self, line: str):
        """Parse a single train stop row from the COPY data."""
        if not line:
            return
            
        parts = line.split("\t")
        if len(parts) < 19:  # Expected number of columns
            return
        
        try:
            stop = {
                "train_id": parts[1],
                "train_departure_time": self._parse_timestamp(parts[2]),
                "station_code": parts[3] if parts[3] != "\\N" else None,
                "station_name": parts[4],
                "scheduled_time": self._parse_timestamp(parts[5]) if parts[5] != "\\N" else None,
                "departure_time": self._parse_timestamp(parts[6]) if parts[6] != "\\N" else None,
                "departed": parts[9] == "t",
                "stop_status": parts[10] if parts[10] != "\\N" else None,
            }
            self.train_stops_data.append(stop)
        except (ValueError, IndexError) as e:
            self.stats["errors"] += 1

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse PostgreSQL timestamp format."""
        if not ts_str or ts_str == "\\N":
            return None
        try:
            # Handle fractional seconds if present
            if "." in ts_str:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
            else:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def migrate_data(self):
        """Migrate parsed data to SQLite database."""
        print("\nMigrating data to SQLite...")
        
        # Group trains by train_id and date
        train_journeys = {}
        for train in self.trains_data:
            if not train["departure_time"]:
                continue
                
            journey_date = train["departure_time"].date()
            key = (train["train_id"], journey_date, train["data_source"])
            
            if key not in train_journeys:
                train_journeys[key] = train
        
        # Insert journeys
        cursor = self.conn.cursor()
        for (train_id, journey_date, data_source), train in train_journeys.items():
            try:
                # Check if journey already exists
                existing = cursor.execute(
                    """SELECT id FROM train_journeys 
                       WHERE train_id = ? AND journey_date = ? AND data_source = ?""",
                    (train_id, journey_date, data_source)
                ).fetchone()
                
                if existing:
                    self.stats["skipped_duplicates"] += 1
                    continue
                
                # Calculate actual departure time based on delay
                actual_departure = None
                if train["departure_time"] and train["delay_minutes"]:
                    actual_departure = datetime.combine(
                        train["departure_time"].date(),
                        train["departure_time"].time()
                    )
                    # Add delay minutes
                    from datetime import timedelta
                    actual_departure += timedelta(minutes=train["delay_minutes"])
                
                # Insert journey
                cursor.execute("""
                    INSERT INTO train_journeys (
                        train_id, journey_date, line_code, line_name,
                        destination, origin_station_code,
                        terminal_station_code, scheduled_departure,
                        actual_departure, is_cancelled, is_completed,
                        data_source, discovery_track, discovery_station_code,
                        has_complete_journey, stops_count, update_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    train_id,
                    journey_date,
                    train["line_code"] or "??",
                    train["line"],
                    train["destination"],
                    train["origin_station_code"],
                    train["origin_station_code"],  # Assume terminal same as origin for now
                    train["departure_time"],
                    actual_departure,
                    1 if train["status"] == "CANCELLED" else 0,
                    1 if train["status"] in ["DEPARTED", "ARRIVED"] else 0,
                    data_source,
                    train["track"],
                    train["origin_station_code"],
                    0,  # has_complete_journey - will update later
                    0,  # stops_count - will update later
                    1   # update_count
                ))
                
                journey_id = cursor.lastrowid
                self.stats["journeys_created"] += 1
                
                # Insert stops for this journey
                stops_for_train = [
                    s for s in self.train_stops_data 
                    if s["train_id"] == train_id 
                    and s["train_departure_time"]
                    and s["train_departure_time"].date() == journey_date
                ]
                
                stop_sequence = 0
                for stop in sorted(stops_for_train, key=lambda s: s["scheduled_time"] or datetime.max):
                    if not stop["station_code"]:
                        continue
                        
                    # For origin station, use track from train record
                    track = None
                    if stop["station_code"] == train["origin_station_code"]:
                        track = train["track"]
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO journey_stops (
                            journey_id, station_code, station_name,
                            stop_sequence, scheduled_departure,
                            actual_departure, track, has_departed_station,
                            pickup_only, dropoff_only
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        journey_id,
                        stop["station_code"],
                        stop["station_name"],
                        stop_sequence,
                        stop["scheduled_time"],
                        stop["departure_time"],
                        track,
                        1 if stop["departed"] else 0,
                        0,  # pickup_only
                        0   # dropoff_only
                    ))
                    
                    if cursor.rowcount > 0:
                        stop_sequence += 1
                        self.stats["stops_created"] += 1
                
                # Update journey with stop count
                if stop_sequence > 0:
                    cursor.execute(
                        "UPDATE train_journeys SET stops_count = ?, has_complete_journey = 1 WHERE id = ?",
                        (stop_sequence, journey_id)
                    )
                
            except sqlite3.Error as e:
                print(f"  Error inserting journey {train_id} on {journey_date}: {e}")
                self.stats["errors"] += 1
                
        self.conn.commit()

    def print_summary(self):
        """Print migration summary."""
        print("\n" + "="*50)
        print("MIGRATION SUMMARY")
        print("="*50)
        print(f"Trains found in dump:     {self.stats['trains_found']:,}")
        print(f"Journeys created:         {self.stats['journeys_created']:,}")
        print(f"Stops created:           {self.stats['stops_created']:,}")
        print(f"Skipped (duplicates):    {self.stats['skipped_duplicates']:,}")
        print(f"Errors:                  {self.stats['errors']:,}")
        print("="*50)

    def run(self):
        """Run the complete migration process."""
        try:
            self.connect()
            self.parse_postgres_dump()
            self.migrate_data()
            self.print_summary()
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate historical train data from PostgreSQL dump to SQLite"
    )
    parser.add_argument(
        "--dump-file",
        type=Path,
        default=Path("dump.sql"),
        help="Path to PostgreSQL dump file (default: dump.sql)"
    )
    parser.add_argument(
        "--db-file",
        type=Path,
        default=Path("trackrat_v2.db"),
        help="Path to SQLite database file (default: trackrat_v2.db)"
    )
    
    args = parser.parse_args()
    
    # Validate files
    if not args.dump_file.exists():
        print(f"Error: Dump file not found: {args.dump_file}")
        sys.exit(1)
    
    if not args.db_file.exists():
        print(f"Error: Database file not found: {args.db_file}")
        sys.exit(1)
    
    # Run migration
    migrator = HistoricalDataMigrator(args.dump_file, args.db_file)
    migrator.run()


if __name__ == "__main__":
    main()