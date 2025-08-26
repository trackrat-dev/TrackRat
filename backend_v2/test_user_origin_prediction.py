#!/usr/bin/env python3
"""Test script for improved user origin prediction logic"""

import asyncio
import httpx
from datetime import datetime

async def test_prediction_logic():
    """Test that predictions use scheduled times when train hasn't reached user's origin"""
    
    base_url = "http://localhost:8000/api/v2"
    
    print("=" * 60)
    print("Testing User Origin Prediction Logic")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            "name": "Train hasn't reached user's origin (PH)",
            "train_id": "3718",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "from_station": "PH",
            "description": "Should use PH scheduled departure as base for predictions"
        },
        {
            "name": "Train has passed user's origin",
            "train_id": "3718",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "from_station": "TR",  # Earlier station, likely passed
            "description": "Should use current time for predictions"
        },
        {
            "name": "No user origin specified",
            "train_id": "3718",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "from_station": None,
            "description": "Should use default logic (current time or scheduled)"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for test_case in test_cases:
            print(f"\n📋 Test: {test_case['name']}")
            print(f"   {test_case['description']}")
            print("-" * 40)
            
            # Build URL with parameters
            params = {
                "date": test_case["date"],
                "include_predictions": "true",
                "refresh": "true"
            }
            
            if test_case["from_station"]:
                params["from_station"] = test_case["from_station"]
            
            url = f"{base_url}/trains/{test_case['train_id']}"
            
            try:
                response = await client.get(url, params=params, timeout=30.0)
                
                if response.status_code == 200:
                    data = response.json()
                    train = data.get("train", {})
                    
                    print(f"✅ Train {train['train_id']} retrieved")
                    
                    # Find user's origin station if specified
                    if test_case["from_station"]:
                        user_origin_found = False
                        for stop in train.get("stops", []):
                            if stop["station_code"] == test_case["from_station"]:
                                user_origin_found = True
                                scheduled_dep = stop.get("scheduled_departure")
                                predicted_arr = stop.get("predicted_arrival")
                                
                                print(f"\n👤 User's origin: {stop['station_code']} - {stop['station_name']}")
                                print(f"   Scheduled departure: {scheduled_dep}")
                                print(f"   Predicted arrival: {predicted_arr}")
                                
                                if predicted_arr:
                                    print(f"   ⚠️  Prediction exists for origin (should be None)")
                                else:
                                    print(f"   ✅ No prediction for origin (correct)")
                                break
                        
                        if not user_origin_found:
                            print(f"   ⚠️  User's origin {test_case['from_station']} not found in stops")
                    
                    # Show predictions for next few stops
                    print("\n🔮 Predictions for subsequent stops:")
                    predictions_shown = 0
                    for stop in train.get("stops", []):
                        if stop.get("predicted_arrival"):
                            predictions_shown += 1
                            print(f"   {stop['station_code']}: {stop['predicted_arrival']} "
                                  f"(scheduled: {stop.get('scheduled_arrival')})")
                            
                            if predictions_shown >= 3:
                                break
                    
                    if predictions_shown == 0:
                        print("   No predictions found")
                    
                else:
                    print(f"❌ Error: HTTP {response.status_code}")
                    print(f"   Response: {response.text}")
                    
            except httpx.TimeoutException:
                print("⏱️  Request timed out")
            except Exception as e:
                print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed! Check backend logs for detailed prediction logic.")
    print("Look for log entries with 👤 emoji for user origin handling.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_prediction_logic())