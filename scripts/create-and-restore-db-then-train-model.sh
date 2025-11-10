#!/bin/bash
#
# Create and restore PostgreSQL database for TrackRat ML training, then train the model

set -e  # Exit on any error

echo "🛑 Stopping and removing existing container..."
docker stop trackrat-postgres 2>/dev/null || true
docker rm trackrat-postgres 2>/dev/null || true

echo "🚀 Starting fresh PostgreSQL container..."
docker run --name trackrat-postgres \
	-e POSTGRES_USER=postgres \
	-e POSTGRES_PASSWORD=password \
	-e POSTGRES_DB=trackratdb \
	-p 5433:5432 \
	-d postgres:15

echo "⏳ Waiting for PostgreSQL to start..."
sleep 10

# Test connection
echo "🔍 Testing database connection..."
docker exec trackrat-postgres psql -U postgres -d trackratdb -c "SELECT version();" > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    exit 1
fi

# Restore the dump
echo "📥 Restoring database from dump..."
if [ ! -f "2025-08-22-data-dump.sql" ]; then
    echo "❌ Dump file '2025-08-22-data-dump.sql' not found in current directory"
    echo "Please ensure the file exists in: $(pwd)"
    exit 1
fi

# Restore with verbose output but skip non-critical errors
echo "   (Note: Skipping PostgreSQL 17-specific settings that don't exist in PostgreSQL 15)"
docker exec -i trackrat-postgres psql -U postgres -d trackratdb < 2025-08-22-data-dump.sql 2>&1 | \
    grep -v "unrecognized configuration parameter" | \
    grep -v "transaction_timeout" | \
    grep -v "role.*does not exist" | \
    tail -10

# Verify restore
echo "🔍 Verifying data restoration..."
JOURNEY_COUNT=$(docker exec trackrat-postgres psql -U postgres -d trackratdb -t -c "SELECT COUNT(*) FROM train_journeys;")
STOPS_COUNT=$(docker exec trackrat-postgres psql -U postgres -d trackratdb -t -c "SELECT COUNT(*) FROM journey_stops;")

if [ -n "$JOURNEY_COUNT" ] && [ "$JOURNEY_COUNT" -gt 0 ]; then
    echo "✅ Database restored successfully!"
    echo "   📊 Train journeys: $(echo $JOURNEY_COUNT | xargs)"
    echo "   🚏 Journey stops: $(echo $STOPS_COUNT | xargs)"
else
    echo "❌ Database restore failed - no data found"
    exit 1
fi

echo ""
echo "🎉 Database setup complete!"
echo "Connection string: postgresql+asyncpg://postgres:password@localhost:5433/trackratdb"

# Move to backend directory for ML training
echo ""
echo "🤖 Starting ML model training pipeline..."
cd backend_v2

# Export training data
echo "📊 Exporting training data from database..."
TRACKRAT_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5433/trackratdb" \
poetry run python scripts/export_track_training_data.py

if [ ! -f "data/ny_penn_track_training_data.csv" ]; then
    echo "❌ Training data export failed"
    exit 1
fi

# Check if we have ML dependencies
echo "🔧 Installing ML dependencies..."
poetry add pandas scikit-learn numpy --quiet 2>/dev/null || true

# Train the model
echo "🧠 Training Random Forest model..."
poetry run python ml/train_track_predictor.py

# Verify model files were created
if [ -f "ml/models/ny_track_predictor.pkl" ] && [ -f "ml/models/ny_label_encoders.pkl" ] && [ -f "ml/models/ny_track_classes.pkl" ]; then
    echo "✅ Model training complete!"
    echo "   📁 Model files saved in ml/models/"
    echo "   📈 Performance report in ml/reports/"
else
    echo "❌ Model training failed - model files not found"
    exit 1
fi

echo ""
echo "🎯 Complete ML Pipeline Summary:"
echo "   🗄️  Database: $(echo $JOURNEY_COUNT | xargs) journeys, $(echo $STOPS_COUNT | xargs) stops"
echo "   📊 Training data: $(wc -l < data/ny_penn_track_training_data.csv | xargs) samples"
echo "   🤖 Model: Random Forest trained on NY Penn Station tracks"
echo "   🚀 API ready: Use TRACKRAT_DATABASE_URL=\"postgresql+asyncpg://postgres:password@localhost:5433/trackratdb\""
echo ""
echo "Next steps:"
echo "  1. Start API: poetry run uvicorn trackrat.main:app --reload"
echo "  2. Test endpoint: curl 'http://localhost:8000/api/v2/predictions/track?station_code=NY&train_id=3123&journey_date=2024-01-15'"
