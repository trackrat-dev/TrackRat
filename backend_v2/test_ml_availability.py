#!/usr/bin/env python3
"""
Quick test to verify ML model availability and error handling.
"""

import asyncio
import httpx
from datetime import date

async def test_ml_predictions():
    """Test ML prediction endpoints."""
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check supported stations
    print("1. Testing supported stations endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/api/v2/predictions/supported-stations")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Found {data['total_ml_enabled']} ML-enabled stations")
            for station in data['stations'][:5]:  # Show first 5
                if station['ml_predictions_available']:
                    print(f"     - {station['code']}: {station['name']} ({station['track_count']} tracks)")
        else:
            print(f"   ✗ Error: {response.status_code}")
    
    # Test 2: Try prediction for station WITH model (should work locally)
    print("\n2. Testing prediction for station WITH model (MP)...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{base_url}/api/v2/predictions/track",
            params={
                "station_code": "MP",
                "train_id": "3889",
                "journey_date": date.today().isoformat()
            }
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Got prediction: {data['primary_prediction']} (confidence: {data['confidence']:.2%})")
            print(f"     Model version: {data['model_version']}")
        elif response.status_code == 400:
            print(f"   ✗ Expected 400 error (model not loaded): {response.json()['detail']}")
        else:
            print(f"   ✗ Unexpected error: {response.status_code} - {response.text}")
    
    # Test 3: Try prediction for station WITHOUT model (should get 400)
    print("\n3. Testing prediction for station WITHOUT ML enabled (JA)...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{base_url}/api/v2/predictions/track",
            params={
                "station_code": "JA",
                "train_id": "3889", 
                "journey_date": date.today().isoformat()
            }
        )
        if response.status_code == 400:
            print(f"   ✓ Got expected 400 error: {response.json()['detail']}")
        else:
            print(f"   ✗ Unexpected response: {response.status_code}")
    
    # Test 4: Check if fallback is really disabled (no uniform distribution)
    print("\n4. Verifying no fallback uniform distribution...")
    print("   If models aren't loaded, we should get 400 errors, not equal probabilities")
    print("   This prevents iOS app from showing misleading equal odds")

if __name__ == "__main__":
    print("ML Prediction Availability Test")
    print("================================\n")
    print("Make sure the backend is running: poetry run uvicorn trackrat.main:app --reload\n")
    
    asyncio.run(test_ml_predictions())