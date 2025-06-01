"""
Unit tests for the data import service.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository
from trackcast.services.data_import import DataImportService


@pytest.fixture
def mock_session():
    """Fixture for a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_train_repo(mock_session):
    """Fixture for a mock train repository."""
    repo = MagicMock(spec=TrainRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def data_import_service(mock_session, mock_train_repo):
    """Fixture for a data import service with mocked dependencies."""
    service = DataImportService(mock_session)
    service.train_repo = mock_train_repo
    return service


def test_detect_file_format(data_import_service):
    """Test file format detection."""
    # Create temp files for testing
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w+") as csv_file, \
         tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as json_file, \
         tempfile.NamedTemporaryFile(suffix=".txt", mode="w+") as txt_file_csv, \
         tempfile.NamedTemporaryFile(suffix=".txt", mode="w+") as txt_file_json:
        
        # Write content to files
        csv_file.write("header1,header2\nvalue1,value2\n")
        csv_file.flush()
        
        json_file.write('{"key": "value"}')
        json_file.flush()
        
        txt_file_csv.write("col1,col2,col3\n1,2,3\n")
        txt_file_csv.flush()
        
        txt_file_json.write('{"data": [1, 2, 3]}')
        txt_file_json.flush()
        
        # Test detection
        assert data_import_service._detect_file_format(Path(csv_file.name)) == "csv"
        assert data_import_service._detect_file_format(Path(json_file.name)) == "json"
        assert data_import_service._detect_file_format(Path(txt_file_csv.name)) == "csv"
        assert data_import_service._detect_file_format(Path(txt_file_json.name)) == "json"


def test_sort_files_by_timestamp(data_import_service):
    """Test sorting files by timestamp in filename."""
    # Create temp files with timestamps in filenames
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with timestamps in filenames
        file_paths = [
            Path(temp_dir) / "trains_2023-05-10T12-30-45.csv",
            Path(temp_dir) / "trains_2023-05-10T10-15-30.csv",
            Path(temp_dir) / "trains_2023-05-11T08-45-00.csv",
        ]
        
        # Touch files to create them
        for file_path in file_paths:
            with open(file_path, "w"):
                pass
        
        # Test sorting
        sorted_files = data_import_service._sort_files_by_timestamp(file_paths)
        
        # Verify order
        expected_order = [
            Path(temp_dir) / "trains_2023-05-10T10-15-30.csv",
            Path(temp_dir) / "trains_2023-05-10T12-30-45.csv",
            Path(temp_dir) / "trains_2023-05-11T08-45-00.csv",
        ]
        
        assert sorted_files == expected_order


def test_standardize_csv_record(data_import_service):
    """Test standardizing CSV records."""
    # Test with various column name formats
    csv_row = {
        "Train_ID": "1234",
        "Destination": "Newark",
        "Track": "5",
        "Departure_Time": "2023-05-10 12:30:45",
        "Status": "ON TIME",
        "Line": "Northeast Corridor",
        "Line_Code": "NEC",
    }
    
    result = data_import_service._standardize_csv_record(csv_row)
    
    assert result["train_id"] == "1234"
    assert result["destination"] == "Newark"
    assert result["track"] == "5"
    assert isinstance(result["departure_time"], datetime)
    assert result["status"] == "ON TIME"
    assert result["line"] == "Northeast Corridor"
    assert result["line_code"] == "NEC"
    
    # Test with different column naming
    csv_row2 = {
        "TRAIN_ID": "5678",
        "DESTINATION": "Trenton",
        "TRACK": "7",
        "DEPARTURE_TIME": "2023-05-10T14:45:00",
        "STATUS": "DELAYED",
        "LINE": "North Jersey Coast",
        "LINECODE": "NJCL",
    }
    
    result2 = data_import_service._standardize_csv_record(csv_row2)
    
    assert result2["train_id"] == "5678"
    assert result2["destination"] == "Trenton"
    assert result2["track"] == "7"
    assert isinstance(result2["departure_time"], datetime)
    assert result2["status"] == "DELAYED"
    assert result2["line"] == "North Jersey Coast"
    assert result2["line_code"] == "NJCL"


def test_standardize_json_record(data_import_service):
    """Test standardizing JSON records."""
    # Test with ISO format date
    json_record = {
        "train_id": "1234",
        "destination": "Newark",
        "track": "5",
        "departure_time": "2023-05-10T12:30:45",
        "status": "ON TIME",
        "line": "Northeast Corridor",
        "line_code": "NEC",
    }
    
    result = data_import_service._standardize_json_record(json_record)
    
    assert result["train_id"] == "1234"
    assert result["destination"] == "Newark"
    assert result["track"] == "5"
    assert isinstance(result["departure_time"], datetime)
    assert result["status"] == "ON TIME"
    assert result["line"] == "Northeast Corridor"
    assert result["line_code"] == "NEC"
    
    # Test with string format date
    json_record2 = {
        "train_id": "5678",
        "destination": "Trenton",
        "track": "7",
        "departure_time": "10-May-2023 02:45:00 PM",
        "status": "DELAYED",
        "line": "North Jersey Coast",
        "line_code": "NJCL",
    }
    
    result2 = data_import_service._standardize_json_record(json_record2)
    
    assert result2["train_id"] == "5678"
    assert result2["destination"] == "Trenton"
    assert result2["track"] == "7"
    assert isinstance(result2["departure_time"], datetime)
    assert result2["status"] == "DELAYED"
    assert result2["line"] == "North Jersey Coast"
    assert result2["line_code"] == "NJCL"


def test_import_train_record_new(data_import_service, mock_train_repo):
    """Test importing a new train record."""
    # Setup mock
    mock_train_repo.get_train_by_id_and_time.return_value = None
    
    # Test data
    train_data = {
        "train_id": "1234",
        "line": "Northeast Corridor",
        "line_code": "NEC",
        "destination": "Newark",
        "departure_time": datetime.fromisoformat("2023-05-10T12:30:45"),
        "track": "5",
        "status": "ON TIME",
    }
    
    current_time = datetime.now()
    
    # Call method
    new_train, updated = data_import_service._import_train_record(train_data, current_time, False)
    
    # Verify
    assert new_train is True
    assert updated is False
    
    # Verify repository calls
    mock_train_repo.get_train_by_id_and_time.assert_called_once_with(
        train_data["train_id"], train_data["departure_time"]
    )
    
    # Check create_train call
    create_call_args = mock_train_repo.create_train.call_args[0][0]
    assert create_call_args["train_id"] == "1234"
    assert create_call_args["line"] == "Northeast Corridor"
    assert create_call_args["track"] == "5"
    assert create_call_args["track_assigned_at"] == current_time


def test_import_train_record_update(data_import_service, mock_train_repo):
    """Test updating an existing train record."""
    # Setup mock
    mock_existing_train = MagicMock(spec=Train)
    mock_existing_train.train_id = "1234"
    mock_train_repo.get_train_by_id_and_time.return_value = mock_existing_train
    
    # Test data
    train_data = {
        "train_id": "1234",
        "line": "Northeast Corridor",
        "line_code": "NEC",
        "destination": "Newark",
        "departure_time": datetime.fromisoformat("2023-05-10T12:30:45"),
        "track": "5",
        "status": "DELAYED",
    }
    
    current_time = datetime.now()
    
    # Call method
    new_train, updated = data_import_service._import_train_record(train_data, current_time, True)
    
    # Verify
    assert new_train is False
    assert updated is True
    
    # Verify repository calls
    mock_train_repo.get_train_by_id_and_time.assert_called_once_with(
        train_data["train_id"], train_data["departure_time"]
    )
    
    # Check update_train call
    update_call_args = mock_train_repo.update_train.call_args
    assert update_call_args[0][0] == mock_existing_train
    
    update_data = update_call_args[0][1]
    assert update_data["track"] == "5"
    assert update_data["status"] == "DELAYED"
    assert update_data["line"] == "Northeast Corridor"


def test_import_train_record_skip_update(data_import_service, mock_train_repo):
    """Test skipping update for existing train when overwrite is False."""
    # Setup mock
    mock_existing_train = MagicMock(spec=Train)
    mock_existing_train.train_id = "1234"
    mock_train_repo.get_train_by_id_and_time.return_value = mock_existing_train
    
    # Test data
    train_data = {
        "train_id": "1234",
        "line": "Northeast Corridor",
        "line_code": "NEC",
        "destination": "Newark",
        "departure_time": datetime.fromisoformat("2023-05-10T12:30:45"),
        "track": "5",
        "status": "DELAYED",
    }
    
    current_time = datetime.now()
    
    # Call method with overwrite=False
    new_train, updated = data_import_service._import_train_record(train_data, current_time, False)
    
    # Verify
    assert new_train is False
    assert updated is False
    
    # Verify repository calls
    mock_train_repo.get_train_by_id_and_time.assert_called_once_with(
        train_data["train_id"], train_data["departure_time"]
    )
    
    # Ensure update_train was not called
    mock_train_repo.update_train.assert_not_called()


@patch("trackcast.services.data_import.Path")
@patch("trackcast.services.data_import.open")
def test_import_csv_file(mock_open, mock_path, data_import_service):
    """Test importing data from a CSV file."""
    # Setup mock Path
    mock_file_path = MagicMock()
    mock_file_path.__str__.return_value = "/path/to/test.csv"
    
    # Setup mock CSV reader
    mock_csv_context = MagicMock()
    mock_csv_reader = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_csv_context
    
    # Mock CSV data
    csv_rows = [
        {
            "Train_ID": "1234",
            "Destination": "Newark",
            "Track": "5",
            "Departure_Time": "2023-05-10T12:30:45",
            "Status": "ON TIME",
            "Line": "Northeast Corridor",
            "Line_Code": "NEC",
        },
        {
            "Train_ID": "5678",
            "Destination": "Trenton",
            "Track": "7",
            "Departure_Time": "2023-05-10T14:45:00",
            "Status": "DELAYED",
            "Line": "North Jersey Coast",
            "Line_Code": "NJCL",
        },
    ]
    
    # Setup import_train_record to return values
    data_import_service._import_train_record = MagicMock()
    data_import_service._import_train_record.side_effect = [(True, False), (True, False)]
    
    # Mock csv.DictReader
    with patch("csv.DictReader", return_value=csv_rows):
        # Call method
        success, stats = data_import_service._import_csv_file(mock_file_path, False)
    
    # Verify
    assert success is True
    assert stats["records_processed"] == 2
    assert stats["trains_new"] == 2
    assert stats["trains_updated"] == 0
    assert data_import_service._import_train_record.call_count == 2


@patch("json.load")
def test_import_json_file(mock_json_load, data_import_service):
    """Test importing data from a JSON file."""
    # Setup mock Path
    mock_file_path = MagicMock()
    mock_file_path.__str__.return_value = "/path/to/test.json"
    
    # Mock JSON data - processed format
    json_data = [
        {
            "train_id": "1234",
            "destination": "Newark",
            "track": "5",
            "departure_time": "2023-05-10T12:30:45",
            "status": "ON TIME",
            "line": "Northeast Corridor",
            "line_code": "NEC",
        },
        {
            "train_id": "5678",
            "destination": "Trenton",
            "track": "7",
            "departure_time": "2023-05-10T14:45:00",
            "status": "DELAYED",
            "line": "North Jersey Coast",
            "line_code": "NJCL",
        },
    ]
    
    mock_json_load.return_value = json_data
    
    # Setup import_train_record to return values
    data_import_service._import_train_record = MagicMock()
    data_import_service._import_train_record.side_effect = [(True, False), (True, False)]
    
    # Open mock
    with patch("builtins.open", MagicMock()):
        # Call method
        success, stats = data_import_service._import_json_file(mock_file_path, False)
    
    # Verify
    assert success is True
    assert stats["records_processed"] == 2
    assert stats["trains_new"] == 2
    assert stats["trains_updated"] == 0
    assert data_import_service._import_train_record.call_count == 2


@patch("json.load")
def test_import_json_file_api_format(mock_json_load, data_import_service):
    """Test importing data from a JSON file in raw API format."""
    # Setup mock Path
    mock_file_path = MagicMock()
    mock_file_path.__str__.return_value = "/path/to/test.json"
    
    # Mock JSON data - raw API format
    json_data = {
        "timestamp": "2023-05-10T12:00:00",
        "data": {
            "ITEMS": [
                {
                    "TRAIN_ID": "1234",
                    "DESTINATION": "Newark",
                    "TRACK": "5",
                    "SCHED_DEP_DATE": "10-May-2023 12:30:45 PM",
                    "STATUS": "ON TIME",
                    "LINE": "Northeast Corridor",
                    "LINECODE": "NEC",
                },
                {
                    "TRAIN_ID": "5678",
                    "DESTINATION": "Trenton",
                    "TRACK": "7",
                    "SCHED_DEP_DATE": "10-May-2023 02:45:00 PM",
                    "STATUS": "DELAYED",
                    "LINE": "North Jersey Coast",
                    "LINECODE": "NJCL",
                },
            ]
        }
    }
    
    mock_json_load.return_value = json_data
    
    # Setup import_train_record to return values
    data_import_service._import_train_record = MagicMock()
    data_import_service._import_train_record.side_effect = [(True, False), (True, False)]
    
    # Open mock
    with patch("builtins.open", MagicMock()):
        # Call method
        success, stats = data_import_service._import_json_file(mock_file_path, False)
    
    # Verify
    assert success is True
    assert stats["records_processed"] == 2
    assert stats["trains_new"] == 2
    assert stats["trains_updated"] == 0
    assert data_import_service._import_train_record.call_count == 2


@patch("trackcast.services.data_import.Path")
@patch("trackcast.services.data_import.glob")
def test_import_data_integration(mock_glob, mock_path, data_import_service):
    """Test the full import_data method."""
    # Setup mocks
    mock_source_path = MagicMock()
    mock_source_path.exists.return_value = True
    mock_source_path.is_dir.return_value = True
    mock_path.return_value = mock_source_path
    
    # Setup mock file paths
    mock_file_path1 = MagicMock()
    mock_file_path1.__str__.return_value = "/path/to/test1.csv"
    
    mock_file_path2 = MagicMock()
    mock_file_path2.__str__.return_value = "/path/to/test2.json"
    
    mock_source_path.glob.return_value = [mock_file_path1, mock_file_path2]
    
    # Mock sort_files_by_timestamp
    data_import_service._sort_files_by_timestamp = MagicMock(
        return_value=[mock_file_path1, mock_file_path2]
    )
    
    # Mock detect_file_format
    data_import_service._detect_file_format = MagicMock()
    data_import_service._detect_file_format.side_effect = ["csv", "json"]
    
    # Mock import_csv_file and import_json_file
    data_import_service._import_csv_file = MagicMock(
        return_value=(True, {
            "records_processed": 2,
            "trains_new": 2,
            "trains_updated": 0,
            "errors": [],
        })
    )
    
    data_import_service._import_json_file = MagicMock(
        return_value=(True, {
            "records_processed": 3,
            "trains_new": 1,
            "trains_updated": 2,
            "errors": [],
        })
    )
    
    # Call method
    success, stats = data_import_service.import_data(
        source_dir="/path/to/data",
        file_format=None,
        file_pattern=None,
        overwrite=False
    )
    
    # Verify
    assert success is True
    assert stats["files_processed"] == 2
    assert stats["records_processed"] == 5  # 2 + 3
    assert stats["trains_new"] == 3  # 2 + 1
    assert stats["trains_updated"] == 2  # 0 + 2
    
    # Verify file processing
    data_import_service._import_csv_file.assert_called_once_with(mock_file_path1, False)
    data_import_service._import_json_file.assert_called_once_with(mock_file_path2, False)