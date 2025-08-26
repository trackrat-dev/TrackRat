#!/usr/bin/env python
"""
Test script to verify that origin station predictions are properly filtered.
"""

import asyncio
import httpx
from datetime import datetime

async def test_origin_prediction_filtering():
    """Test that predictions are filtered for the user's origin station."""
    
    base_url = "http://localhost:8000/api/v2"
    
    # Test train details WITHOUT from_station (should include all predictions)
    print("=" * 60)
    print("TEST 1: Fetching train details WITHOUT from_station parameter")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/trains/3879")
        if response.status_code == 200:
            data = response.json()
            train = data.get("train", {})
            stops = train.get("stops", [])
            
            # Count stops with predictions
            stops_with_predictions = [
                s for s in stops 
                if s.get("predicted_arrival") is not None
            ]
            
            print(f"✅ Request successful")
            print(f"   Total stops: {len(stops)}")
            print(f"   Stops with predictions: {len(stops_with_predictions)}")
            
            # Show first few stops
            for i, stop in enumerate(stops[:3]):
                station_code = stop.get("station", {}).get("code", "?")
                station_name = stop.get("station", {}).get("name", "?")
                has_prediction = "✓" if stop.get("predicted_arrival") else "✗"
                print(f"   Stop {i}: {station_code} ({station_name}) - Prediction: {has_prediction}")
        else:
            print(f"❌ Request failed: {response.status_code}")
    
    print()
    
    # Test train details WITH from_station (should filter origin prediction)
    from_station = "NY"  # Example: NY Penn Station
    print("=" * 60)
    print(f"TEST 2: Fetching train details WITH from_station={from_station}")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{base_url}/trains/3879",
            params={"from_station": from_station}
        )
        
        if response.status_code == 200:
            data = response.json()
            train = data.get("train", {})
            stops = train.get("stops", [])
            
            # Count stops with predictions
            stops_with_predictions = [
                s for s in stops 
                if s.get("predicted_arrival") is not None
            ]
            
            # Check if origin station has prediction
            origin_stop = next(
                (s for s in stops if s.get("station", {}).get("code") == from_station),
                None
            )
            
            print(f"✅ Request successful")
            print(f"   Total stops: {len(stops)}")
            print(f"   Stops with predictions: {len(stops_with_predictions)}")
            
            if origin_stop:
                has_prediction = origin_stop.get("predicted_arrival") is not None
                samples = origin_stop.get("predicted_arrival_samples")
                print(f"   Origin station ({from_station}):")
                print(f"     - Has prediction: {'YES ❌ (BUG!)' if has_prediction else 'NO ✅ (CORRECT)'}")
                print(f"     - Samples: {samples}")
            else:
                print(f"   ⚠️  Origin station {from_station} not found in stops")
            
            # Show first few stops
            for i, stop in enumerate(stops[:3]):
                station_code = stop.get("station", {}).get("code", "?")
                station_name = stop.get("station", {}).get("name", "?")
                has_prediction = "✓" if stop.get("predicted_arrival") else "✗"
                is_origin = " (ORIGIN)" if station_code == from_station else ""
                print(f"   Stop {i}: {station_code} ({station_name}) - Prediction: {has_prediction}{is_origin}")
        else:
            print(f"❌ Request failed: {response.status_code}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print()
    print("Expected behavior:")
    print("1. Without from_station: All stops (except actual origin) should have predictions")
    print("2. With from_station=NY: NY station should NOT have a prediction")
    print("3. The fix filters predictions at the API layer for better UX")

if __name__ == "__main__":
    print(f"Testing origin prediction filtering")
    print(f"Time: {datetime.now()}")
    print()
    asyncio.run(test_origin_prediction_filtering())