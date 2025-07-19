#!/usr/bin/env python3
"""
LIRR Penn Station Track Monitor - Corrected version using actual stop ID
Penn Station stop_id is 237 (stop_code: NYK)
"""

import requests
from datetime import datetime
from collections import defaultdict
import json

# GTFS-RT feed URL
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"

# Penn Station stop ID from GTFS stops.txt
PENN_STATION_ID = "237"

class LIRRPennTrackMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'LIRR Track Monitor/1.0'})
        
    def fetch_feed(self):
        """Fetch the GTFS-RT feed"""
        try:
            response = self.session.get(FEED_URL, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Error fetching feed: {e}")
            return None
    
    def parse_extension_data(self, data):
        """Parse MTA Railroad extension data for track and status"""
        track = None
        train_status = None
        
        pos = 0
        while pos < len(data):
            if pos >= len(data):
                break
                
            tag = data[pos]
            pos += 1
            
            field_num = tag >> 3
            wire_type = tag & 0x7
            
            if field_num == 1 and wire_type == 2:  # track field
                if pos >= len(data):
                    break
                length = data[pos]
                pos += 1
                
                if pos + length <= len(data):
                    track = data[pos:pos + length].decode('utf-8', errors='ignore')
                    pos += length
            elif field_num == 2 and wire_type == 2:  # trainStatus field
                if pos >= len(data):
                    break
                length = data[pos]
                pos += 1
                
                if pos + length <= len(data):
                    train_status = data[pos:pos + length].decode('utf-8', errors='ignore')
                    pos += length
            else:
                if wire_type == 2:  # length-delimited
                    if pos >= len(data):
                        break
                    length = data[pos]
                    pos += 1 + length
                else:
                    pos += 1
        
        return track, train_status
    
    def get_penn_departures(self, feed_data):
        """Extract all Penn Station departures with track assignments"""
        from google.transit import gtfs_realtime_pb2
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(feed_data)
        
        penn_departures = []
        extension_tag = b'\xea>'  # Field 1005 tag
        
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                trip = entity.trip_update
                trip_id = trip.trip.trip_id if trip.trip.HasField('trip_id') else 'Unknown'
                route_id = trip.trip.route_id if trip.trip.HasField('route_id') else 'Unknown'
                
                for stop_update in trip.stop_time_update:
                    stop_id = stop_update.stop_id if stop_update.HasField('stop_id') else 'Unknown'
                    
                    # Only process Penn Station stop
                    if stop_id != PENN_STATION_ID:
                        continue
                    
                    # Only departures (not arrivals)
                    if not stop_update.HasField('departure'):
                        continue
                    
                    departure_time = datetime.fromtimestamp(stop_update.departure.time)
                    
                    # Parse track from extension
                    track = None
                    train_status = None
                    
                    stop_bytes = stop_update.SerializeToString()
                    if extension_tag in stop_bytes:
                        pos = stop_bytes.find(extension_tag)
                        if pos >= 0 and pos + 2 < len(stop_bytes):
                            msg_len = stop_bytes[pos + 2]
                            if pos + 3 + msg_len <= len(stop_bytes):
                                extension_data = stop_bytes[pos + 3:pos + 3 + msg_len]
                                track, train_status = self.parse_extension_data(extension_data)
                    
                    penn_departures.append({
                        'trip_id': trip_id,
                        'route_id': route_id,
                        'track': track or 'TBD',
                        'train_status': train_status,
                        'departure_time': departure_time
                    })
        
        return penn_departures
    
    def display_results(self, departures):
        """Display results in a clean format"""
        if not departures:
            print("\nNo Penn Station departures found")
            return
        
        # Sort by departure time
        departures.sort(key=lambda x: x['departure_time'])
        
        # Group by track
        by_track = defaultdict(list)
        for dep in departures:
            by_track[dep['track']].append(dep)
        
        print(f"\n{'='*80}")
        print(f"LIRR NEW YORK PENN STATION (NYK) DEPARTURES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"Found {len(departures)} departures from Penn Station\n")
        
        # Show all departures
        print("ALL PENN STATION DEPARTURES:")
        print(f"{'Time':<8} {'Track':<8} {'Train ID':<20} {'Route':<10} {'Status':<15}")
        print("-" * 70)
        
        for dep in departures:
            time_str = dep['departure_time'].strftime('%H:%M')
            status_str = dep['train_status'] or ''
            print(f"{time_str:<8} {dep['track']:<8} {dep['trip_id']:<20} {dep['route_id']:<10} {status_str:<15}")
        
        # Track summary
        print(f"\n{'TRACK ASSIGNMENTS AT PENN STATION:'}")
        print("-" * 40)
        # Sort tracks
        track_counts = []
        for track, deps in by_track.items():
            if track == 'TBD':
                sort_key = (1, 0)  # Put TBD last
            elif track.isdigit():
                sort_key = (0, int(track))
            else:
                sort_key = (0, ord(track[0]))  # Sort letters
            track_counts.append((track, len(deps), sort_key))
        
        track_counts.sort(key=lambda x: x[2])
        
        for track, count, _ in track_counts:
            print(f"Track {track:<6}: {count} trains")
        
        # Save to JSON
        output_file = f"lirr_penn_tracks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'penn_station_id': PENN_STATION_ID,
            'penn_station_code': 'NYK',
            'total_departures': len(departures),
            'departures': [
                {
                    'trip_id': d['trip_id'],
                    'route_id': d['route_id'],
                    'track': d['track'],
                    'train_status': d['train_status'],
                    'departure_time': d['departure_time'].isoformat()
                }
                for d in departures
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nData saved to: {output_file}")
        
        # Print train IDs summary
        print(f"\n{'TRAIN IDs DEPARTING FROM PENN STATION:'}")
        print("-" * 40)
        train_ids = sorted(set(d['trip_id'] for d in departures))
        for i, train_id in enumerate(train_ids):
            if i % 4 == 0:
                print()
            print(f"{train_id:<20}", end="")
        print()

def main():
    """Main function"""
    monitor = LIRRPennTrackMonitor()
    
    print("Fetching LIRR GTFS-RT feed...")
    print(f"Looking for Penn Station (stop_id: {PENN_STATION_ID}, code: NYK)")
    
    feed_data = monitor.fetch_feed()
    
    if not feed_data:
        print("Failed to fetch feed")
        return
    
    print(f"Feed size: {len(feed_data)} bytes")
    
    # Get Penn Station departures
    departures = monitor.get_penn_departures(feed_data)
    
    # Display results
    monitor.display_results(departures)

if __name__ == "__main__":
    main()