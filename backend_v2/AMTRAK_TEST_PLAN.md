# Amtrak Integration Test Plan

## Overview

This document outlines a comprehensive testing strategy for the Amtrak train collection integration in Backend V2. The plan covers unit tests, integration tests, and end-to-end tests to ensure robust and reliable operation.

## Test Categories

### 1. Unit Tests (Isolated Component Testing)

#### A. Amtrak Client Tests (`tests/unit/collectors/amtrak/test_client.py`)

**Purpose**: Verify HTTP client behavior with mocked responses

**Test Cases**:
1. **Successful API Response**
   - Mock successful Amtrak API response
   - Verify proper parsing into AmtrakTrainData models
   - Check cache behavior (subsequent calls use cache)

2. **API Error Handling**
   - Mock HTTP 500 error → verify retry logic
   - Mock timeout → verify timeout handling
   - Mock invalid JSON → verify error handling

3. **Cache Management**
   - Test cache TTL expiration (60 seconds)
   - Test cache clearing functionality
   - Test get_train_by_id from cache

4. **Data Validation**
   - Test with missing optional fields (objectID)
   - Test with invalid station data
   - Test with malformed time strings

#### B. Discovery Collector Tests (`tests/unit/collectors/amtrak/test_discovery.py`)

**Purpose**: Test train discovery logic

**Test Cases**:
1. **NYP Station Filtering**
   - Mock trains with NYP stops → verify discovered
   - Mock trains without NYP → verify filtered out
   - Test edge cases (NYP as origin/destination only)

2. **Discovery Results**
   - Verify correct train ID extraction
   - Test duplicate handling
   - Verify result format matches expected structure

#### C. Journey Collector Tests (`tests/unit/collectors/amtrak/test_journey.py`)

**Purpose**: Test journey data transformation

**Test Cases**:
1. **Data Conversion**
   - Test Amtrak → TrainJourney conversion
   - Verify train ID prefixing (A + train number)
   - Test station code mapping (NYP → NY, etc.)
   - Test time parsing (ISO8601 with timezone)

2. **Stop Processing**
   - Test filtering to only tracked stations
   - Verify stop sequence numbering
   - Test status mapping (Departed → DEPARTED, etc.)

3. **Edge Cases**
   - Train with no tracked stations → None result
   - Missing time data → graceful handling
   - Cancelled/terminated train status

#### D. Station Mapping Tests (`tests/unit/config/test_stations.py`)

**Purpose**: Verify station code conversions

**Test Cases**:
1. **Code Mapping**
   - Test all mapped stations (NYP→NY, NWK→NP, etc.)
   - Test unmapped stations → None
   - Test case sensitivity

### 2. Integration Tests (Component Interaction)

#### A. Database Integration (`tests/integration/test_amtrak_database.py`)

**Purpose**: Test database operations with new schema

**Test Cases**:
1. **Data Source Field**
   - Create journeys with data_source='AMTRAK'
   - Verify unique constraint includes data_source
   - Test querying by data_source

2. **Journey Storage**
   - Store Amtrak journey with stops
   - Update existing Amtrak journey
   - Test concurrent updates

3. **Mixed Data Queries**
   - Query departures with both NJT and AMTRAK sources
   - Verify sorting and filtering
   - Test pagination with mixed sources

#### B. Scheduler Integration (`tests/integration/test_scheduler_amtrak.py`)

**Purpose**: Test scheduler with both collectors

**Test Cases**:
1. **Job Scheduling**
   - Verify Amtrak discovery job creation
   - Test job execution triggers
   - Verify parallel execution with NJT

2. **Collection Flow**
   - Mock discovery → verify journey collection scheduled
   - Test error handling in collection pipeline
   - Verify database updates

#### C. Service Layer (`tests/integration/test_departure_service_amtrak.py`)

**Purpose**: Test departure service with mixed data

**Test Cases**:
1. **Multi-Source Queries**
   - Create NJT and Amtrak test data
   - Query departures → verify both returned
   - Test data_source field in responses

2. **JIT Updates**
   - Verify JIT only refreshes NJT trains
   - Test Amtrak trains bypass JIT
   - Check freshness calculations

### 3. End-to-End Tests (Full System Flow)

#### A. Collection Pipeline (`tests/e2e/test_amtrak_collection.py`)

**Purpose**: Test complete data flow

**Test Scenario**:
```python
async def test_full_amtrak_collection():
    # 1. Run Amtrak discovery
    # 2. Verify trains discovered and stored
    # 3. Run journey collection for discovered trains
    # 4. Verify complete journey data stored
    # 5. Query via API → verify response
```

#### B. API Response Tests (`tests/e2e/test_api_mixed_sources.py`)

**Purpose**: Verify API serves mixed data correctly

**Test Cases**:
1. **Departure Endpoint**
   ```
   GET /api/trains/departures?from=NY&to=TR
   - Verify includes both NJT and Amtrak trains
   - Check data_source field present
   - Verify sorting by departure time
   ```

2. **Train Details Endpoint**
   ```
   GET /api/trains/A2150  # Amtrak train
   - Verify returns Amtrak journey
   - Check all stops included
   - Verify data_source='AMTRAK'
   ```

#### C. Performance Tests (`tests/e2e/test_performance.py`)

**Purpose**: Ensure system performs well with additional data

**Test Cases**:
1. **Discovery Performance**
   - Time discovery of 50+ Amtrak trains
   - Verify < 5 second completion

2. **Query Performance**
   - Create 1000 mixed journeys
   - Query departures → verify < 100ms response
   - Test concurrent API requests

### 4. Mock Data Strategy

#### A. Amtrak API Response Fixtures

Create realistic mock responses in `tests/fixtures/amtrak/`:
- `full_response.json` - Complete API response with 50+ trains
- `nyp_trains.json` - Subset of trains serving NYP
- `single_train.json` - Detailed single train for journey tests
- `error_response.json` - API error response

#### B. Database Fixtures

Pre-populate test scenarios:
- Mixed NJT/Amtrak departures from NY
- Completed Amtrak journeys
- Edge cases (cancelled, delayed trains)

### 5. Test Utilities

#### A. Factory Functions

```python
# tests/factories/amtrak.py
def create_amtrak_train_data(
    train_num: str = "2150",
    route: str = "Acela",
    stops_at_nyp: bool = True,
) -> AmtrakTrainData:
    """Factory for creating test Amtrak data"""

def create_amtrak_journey(
    train_id: str = "A2150",
    origin: str = "NY",
    destination: str = "BOS",
) -> TrainJourney:
    """Factory for creating test journey"""
```

#### B. Assertion Helpers

```python
# tests/helpers/assertions.py
def assert_valid_amtrak_journey(journey: TrainJourney):
    """Verify journey has expected Amtrak fields"""
    assert journey.data_source == "AMTRAK"
    assert journey.train_id.startswith("A")
    assert journey.line_code == "AM"
```

### 6. Test Execution Strategy

#### Phase 1: Unit Tests First
1. Implement all unit tests with mocked dependencies
2. Achieve 90%+ coverage on new Amtrak code
3. Verify in isolation before integration

#### Phase 2: Integration Tests
1. Test with real database (PostgreSQL in CI)
2. Use controlled test data
3. Verify component interactions

#### Phase 3: End-to-End Tests
1. Run against test instance
2. Use subset of real Amtrak data
3. Verify complete workflows

### 7. Continuous Integration

#### GitHub Actions Configuration

```yaml
# .github/workflows/test-amtrak.yml
name: Amtrak Integration Tests
on: [push, pull_request]

jobs:
  test:
    steps:
      - name: Unit Tests
        run: pytest tests/unit/collectors/amtrak -v
      
      - name: Integration Tests
        run: pytest tests/integration/*amtrak* -v
        
      - name: E2E Tests
        run: pytest tests/e2e/*amtrak* -v --slow
```

### 8. Coverage Goals

- **Unit Tests**: 95% coverage of new Amtrak code
- **Integration Tests**: All database operations and service interactions
- **E2E Tests**: Critical user paths (discovery → collection → API)

### 9. Error Scenarios to Test

1. **Amtrak API Unavailable**
   - Collector gracefully fails
   - Scheduler continues NJT collection
   - API serves cached/stale data

2. **Partial Data Failures**
   - Some trains fail to collect
   - System continues with successful ones
   - Proper error logging

3. **Data Quality Issues**
   - Invalid station codes
   - Missing required fields
   - Malformed timestamps

### 10. Manual Testing Checklist

Before deployment:
- [ ] Run discovery manually, verify train count
- [ ] Collect journey for one Acela train
- [ ] Query API for NY departures
- [ ] Check logs for errors/warnings
- [ ] Verify database has correct data_source values
- [ ] Test with iOS app (if applicable)

## Summary

This comprehensive test plan ensures the Amtrak integration is:
- **Reliable**: Handles errors gracefully
- **Performant**: Meets response time requirements
- **Maintainable**: Well-tested for future changes
- **Compatible**: Works alongside existing NJT system

The phased approach allows incremental validation, catching issues early before they impact the production system.