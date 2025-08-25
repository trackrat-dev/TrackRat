#!/usr/bin/env python3
"""
Test script for the simple arrival forecaster.

Run this to verify the forecaster is working correctly:
    python test_forecaster.py
"""

import asyncio
import sys
from datetime import datetime

import httpx
from rich import print
from rich.table import Table


async def test_forecaster():
    """Test the arrival forecaster with a real train."""
    
    # Test configuration
    BASE_URL = "http://localhost:8000"
    TEST_TRAIN_ID = "3263"  # Example NJ Transit train
    
    print(f"\n[bold blue]Testing Simple Arrival Forecaster[/bold blue]")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Train: {TEST_TRAIN_ID}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First, try without predictions
            print("[yellow]1. Fetching train WITHOUT predictions...[/yellow]")
            response = await client.get(
                f"{BASE_URL}/api/v2/trains/{TEST_TRAIN_ID}",
                params={"include_predictions": False}
            )
            
            if response.status_code != 200:
                print(f"[red]Error: {response.status_code} - {response.text}[/red]")
                return
            
            data_without = response.json()
            train_data = data_without.get("train", {})
            
            # Then with predictions
            print("[yellow]2. Fetching train WITH predictions...[/yellow]")
            response = await client.get(
                f"{BASE_URL}/api/v2/trains/{TEST_TRAIN_ID}",
                params={"include_predictions": True}
            )
            
            if response.status_code != 200:
                print(f"[red]Error: {response.status_code} - {response.text}[/red]")
                return
            
            data_with = response.json()
            train_data = data_with.get("train", {})
            
            # Display results in a table
            print(f"\n[green]Success! Train {train_data['train_id']} - {train_data['route']['origin']} to {train_data['route']['destination']}[/green]\n")
            
            # Create table for stops
            table = Table(title="Stop Predictions")
            table.add_column("Station", style="cyan")
            table.add_column("Scheduled", style="white")
            table.add_column("Updated", style="yellow")
            table.add_column("Predicted", style="green")
            table.add_column("Samples", style="magenta")
            
            for stop in train_data.get("stops", []):
                station = stop["station"]["name"]
                
                # Format times
                scheduled = stop.get("scheduled_arrival", "")
                if scheduled:
                    scheduled = datetime.fromisoformat(scheduled.replace("Z", "+00:00")).strftime("%H:%M")
                
                updated = stop.get("updated_arrival", "")
                if updated:
                    updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).strftime("%H:%M")
                
                predicted = stop.get("predicted_arrival", "")
                samples = ""
                
                if predicted:
                    predicted = datetime.fromisoformat(predicted.replace("Z", "+00:00")).strftime("%H:%M")
                    samples = str(stop.get("predicted_arrival_samples", 0))
                
                table.add_row(
                    station[:20],  # Truncate long names
                    scheduled or "-",
                    updated or "-",
                    predicted or "-",
                    samples or "-"
                )
            
            print(table)
            
            # Summary statistics
            stops_with_predictions = sum(
                1 for s in train_data.get("stops", [])
                if s.get("predicted_arrival")
            )
            total_stops = len(train_data.get("stops", []))
            
            print(f"\n[bold]Summary:[/bold]")
            print(f"  Total stops: {total_stops}")
            print(f"  Stops with predictions: {stops_with_predictions}")
            print(f"  Coverage: {stops_with_predictions/total_stops*100:.1f}%")
            
            # Check final arrival prediction
            if train_data.get("predicted_arrival"):
                pred_time = datetime.fromisoformat(
                    train_data["predicted_arrival"].replace("Z", "+00:00")
                ).strftime("%H:%M")
                conf = train_data.get("arrival_confidence", 0) * 100
                print(f"\n[bold]Final Arrival Prediction:[/bold]")
                print(f"  Time: {pred_time}")
                print(f"  Confidence: {conf:.0f}%")
            
        except httpx.ConnectError:
            print("[red]Error: Could not connect to API. Is the server running?[/red]")
            print("Start it with: poetry run uvicorn trackrat.main:app --reload")
        except Exception as e:
            print(f"[red]Unexpected error: {e}[/red]")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Check if a train ID was provided
    if len(sys.argv) > 1:
        TEST_TRAIN_ID = sys.argv[1]
    
    asyncio.run(test_forecaster())