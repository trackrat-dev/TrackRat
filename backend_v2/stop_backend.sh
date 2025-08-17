#!/bin/bash
#
# TrackRat V2 Backend Cleanup Script
# Stops the local PostgreSQL container (if running)

echo "🛑 TrackRat V2 Backend Cleanup"
echo "==============================="

# Check if PostgreSQL container is running
if docker ps --format "table {{.Names}}" | grep -q "trackrat-postgres"; then
    echo "🐘 Stopping PostgreSQL container..."
    docker stop trackrat-postgres
    
    echo "🗑️  Removing PostgreSQL container..."
    docker rm trackrat-postgres
    
    echo "✅ PostgreSQL container stopped and removed"
else
    echo "ℹ️  No PostgreSQL container running"
fi

echo "✨ Cleanup complete!"