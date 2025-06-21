"""
Unit tests for performance-related database migrations.
"""

import pytest
from unittest.mock import Mock, patch, call
from sqlalchemy.exc import SQLAlchemyError

from trackcast.db.add_performance_indexes import upgrade, downgrade


class TestPerformanceMigrations:
    """Test class for performance migration functionality."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock()
        session.execute = Mock()
        session.commit = Mock()
        return session
    
    def test_upgrade_creates_all_indexes(self, mock_session):
        """Test that upgrade creates all required performance indexes."""
        with patch('trackcast.db.add_performance_indexes.logger') as mock_logger:
            upgrade(mock_session)
            
            # Should execute 6 CREATE INDEX statements (no ANALYZE statements)
            assert mock_session.execute.call_count == 6
            
            # Verify specific indexes are created
            execute_calls = [call.args[0] for call in mock_session.execute.call_args_list]
            
            # Check that all expected indexes are included
            index_names = [
                'idx_train_stops_train_lookup',
                'idx_train_stops_station_scheduled', 
                'idx_train_stops_departed',
                'idx_train_stops_station_departed_scheduled',
                'idx_train_stops_data_source',
                'idx_trains_id_train_id_departure'
            ]
            
            created_indexes = []
            for execute_call in execute_calls:
                sql_text = str(execute_call).lower()
                if 'create index' in sql_text:
                    for index_name in index_names:
                        if index_name in sql_text:
                            created_indexes.append(index_name)
            
            assert len(created_indexes) == 6, f"Expected 6 indexes, found {len(created_indexes)}: {created_indexes}"
            
            # Verify commit was called
            mock_session.commit.assert_called_once()
            
            # Verify logging
            mock_logger.info.assert_any_call("Adding performance indexes for train stops...")
            mock_logger.info.assert_any_call("Performance indexes migration completed successfully")
    
    def test_upgrade_handles_index_creation_failure(self, mock_session):
        """Test that upgrade properly handles index creation failures."""
        # Mock execute to fail on second call
        mock_session.execute.side_effect = [None, SQLAlchemyError("Index creation failed"), None]
        
        with patch('trackcast.db.add_performance_indexes.logger') as mock_logger:
            with pytest.raises(SQLAlchemyError):
                upgrade(mock_session)
            
            # Should log the error
            mock_logger.error.assert_called_with("Failed to create index: Index creation failed")
    
    def test_upgrade_skips_analyze(self, mock_session):
        """Test that upgrade skips ANALYZE to prevent blocking issues."""
        with patch('trackcast.db.add_performance_indexes.logger') as mock_logger:
            upgrade(mock_session)
            
            # Verify no ANALYZE commands were executed
            execute_calls = [str(call.args[0]) for call in mock_session.execute.call_args_list]
            analyze_calls = [call for call in execute_calls if 'analyze' in call.lower()]
            assert len(analyze_calls) == 0, "Should not execute any ANALYZE commands"
            
            # Should log that ANALYZE is being skipped
            mock_logger.info.assert_any_call("Skipping ANALYZE - statistics will be updated by autovacuum")
            
            # Should still commit
            mock_session.commit.assert_called_once()
    
    def test_downgrade_drops_all_indexes(self, mock_session):
        """Test that downgrade drops all performance indexes."""
        with patch('trackcast.db.add_performance_indexes.logger') as mock_logger:
            downgrade(mock_session)
            
            # Should execute 6 DROP INDEX statements
            assert mock_session.execute.call_count == 6
            
            # Verify specific indexes are dropped
            execute_calls = [call.args[0] for call in mock_session.execute.call_args_list]
            
            expected_drops = [
                'idx_train_stops_train_lookup',
                'idx_train_stops_station_scheduled',
                'idx_train_stops_departed', 
                'idx_train_stops_station_departed_scheduled',
                'idx_train_stops_data_source',
                'idx_trains_id_train_id_departure'
            ]
            
            dropped_indexes = []
            for execute_call in execute_calls:
                sql_text = str(execute_call).lower()
                if 'drop index' in sql_text:
                    for index_name in expected_drops:
                        if index_name in sql_text:
                            dropped_indexes.append(index_name)
            
            assert len(dropped_indexes) == 6, f"Expected 6 index drops, found {len(dropped_indexes)}"
            
            # Verify commit was called
            mock_session.commit.assert_called_once()
            
            # Verify logging
            mock_logger.info.assert_any_call("Removing performance indexes...")
            mock_logger.info.assert_any_call("Performance indexes rollback completed")
    
    def test_downgrade_handles_drop_failure(self, mock_session):
        """Test that downgrade properly handles index drop failures."""
        # Mock execute to fail on third call
        mock_session.execute.side_effect = [None, None, SQLAlchemyError("Index drop failed")]
        
        with patch('trackcast.db.add_performance_indexes.logger') as mock_logger:
            with pytest.raises(SQLAlchemyError):
                downgrade(mock_session)
            
            # Should log the error
            mock_logger.error.assert_called_with("Failed to drop index idx_train_stops_departed: Index drop failed")
    
    def test_upgrade_uses_if_not_exists(self, mock_session):
        """Test that upgrade uses IF NOT EXISTS for idempotency."""
        upgrade(mock_session)
        
        # Check that all CREATE INDEX statements use IF NOT EXISTS
        execute_calls = [call.args[0] for call in mock_session.execute.call_args_list]
        
        create_index_calls = [
            str(call) for call in execute_calls 
            if 'create index' in str(call).lower()
        ]
        
        for sql in create_index_calls:
            assert 'if not exists' in sql.lower(), f"CREATE INDEX should use IF NOT EXISTS: {sql}"
    
    def test_downgrade_uses_if_exists(self, mock_session):
        """Test that downgrade uses IF EXISTS for idempotency.""" 
        downgrade(mock_session)
        
        # Check that all DROP INDEX statements use IF EXISTS
        execute_calls = [call.args[0] for call in mock_session.execute.call_args_list]
        
        drop_index_calls = [
            str(call) for call in execute_calls
            if 'drop index' in str(call).lower()
        ]
        
        for sql in drop_index_calls:
            assert 'if exists' in sql.lower(), f"DROP INDEX should use IF EXISTS: {sql}"
    
    def test_migration_index_definitions(self, mock_session):
        """Test that migration creates indexes with correct definitions."""
        upgrade(mock_session)
        
        execute_calls = [str(call.args[0]) for call in mock_session.execute.call_args_list]
        
        # Test specific index definitions
        index_tests = [
            ('idx_train_stops_train_lookup', 'train_id, train_departure_time, scheduled_time'),
            ('idx_train_stops_station_scheduled', 'station_code, scheduled_time'),
            ('idx_train_stops_departed', 'departed'),
            ('idx_train_stops_station_departed_scheduled', 'station_code, departed, scheduled_time'),
            ('idx_train_stops_data_source', 'data_source'),
            ('idx_trains_id_train_id_departure', 'id, train_id, departure_time'),
        ]
        
        for index_name, expected_columns in index_tests:
            # Find the CREATE INDEX statement for this index
            matching_sql = None
            for sql in execute_calls:
                if index_name in sql.lower() and 'create index' in sql.lower():
                    matching_sql = sql
                    break
            
            assert matching_sql is not None, f"Could not find CREATE INDEX for {index_name}"
            
            # Verify the columns are included (basic check)
            # Note: This is a simplified check - actual column order might vary
            for column in expected_columns.split(', '):
                assert column.strip() in matching_sql.lower(), f"Column {column} not found in {index_name} definition"
    
    def test_migration_partial_indexes(self, mock_session):
        """Test that partial indexes are created with WHERE clauses."""
        upgrade(mock_session)
        
        execute_calls = [str(call.args[0]) for call in mock_session.execute.call_args_list]
        
        # Find statements that should have WHERE clauses
        partial_indexes = [
            'idx_train_stops_station_scheduled',
            'idx_train_stops_station_departed_scheduled'
        ]
        
        for index_name in partial_indexes:
            matching_sql = None
            for sql in execute_calls:
                if index_name in sql.lower() and 'create index' in sql.lower():
                    matching_sql = sql
                    break
            
            assert matching_sql is not None, f"Could not find CREATE INDEX for {index_name}"
            assert 'where' in matching_sql.lower(), f"Partial index {index_name} should have WHERE clause"
            assert 'station_code is not null' in matching_sql.lower(), f"Partial index {index_name} should filter NULL station codes"


# CLI tests skipped - the migrate_performance_indexes command is integrated
# into the existing migration system rather than as a separate CLI command


class TestMigrationSystemIntegration:
    """Test integration with the main migration system."""
    
    def test_performance_migration_included_in_run_migrations(self):
        """Test that performance migration is included in the main migration system."""
        from trackcast.db.migrations import run_migrations
        
        # Mock session
        mock_session = Mock()
        
        # Mock all migration functions to avoid actual database calls
        with patch('trackcast.db.migrations.add_delay_minutes_column') as mock1, \
             patch('trackcast.db.migrations.create_train_stops_table') as mock2, \
             patch('trackcast.db.migrations.update_train_stops_schema') as mock3, \
             patch('trackcast.db.migrations.add_stop_query_indexes') as mock4, \
             patch('trackcast.db.migrations.add_origin_station_columns') as mock5, \
             patch('trackcast.db.migrations.add_data_source_column') as mock6, \
             patch('trackcast.db.migrations.add_data_source_to_train_stops') as mock7, \
             patch('trackcast.db.migrations.add_train_stops_lifecycle_fields') as mock8, \
             patch('trackcast.db.migrations.update_train_stop_unique_constraint') as mock9, \
             patch('trackcast.db.migrations.remove_audit_trail_fields') as mock10, \
             patch('trackcast.db.migrations.add_performance_indexes') as mock_perf:
            
            # Configure all mocks to return success
            success_result = {"status": "success", "message": "Migration completed"}
            for mock_func in [mock1, mock2, mock3, mock4, mock5, mock6, mock7, mock8, mock9, mock10, mock_perf]:
                mock_func.return_value = success_result
            
            # Run migrations
            results = run_migrations(mock_session)
            
            # Verify performance migration was called
            mock_perf.assert_called_once_with(mock_session)
            
            # Verify it's included in results
            migration_names = [result['name'] for result in results]
            assert 'add_performance_indexes' in migration_names, "Performance migration should be included in migration list"
            
            # Verify it's at the end (appropriate for performance improvements)
            assert migration_names[-1] == 'add_performance_indexes', "Performance migration should be last"
    
    def test_performance_migration_wrapper_calls_upgrade(self):
        """Test that the migration wrapper correctly calls the upgrade function."""
        from trackcast.db.migrations import add_performance_indexes
        
        mock_session = Mock()
        
        with patch('trackcast.db.add_performance_indexes.upgrade') as mock_upgrade:
            result = add_performance_indexes(mock_session)
            
            # Verify upgrade was called with session
            mock_upgrade.assert_called_once_with(mock_session)
            
            # Verify successful result
            assert result['status'] == 'success'
            assert 'Performance indexes added successfully' in result['message']
    
    def test_performance_migration_wrapper_handles_errors(self):
        """Test that the migration wrapper properly handles errors."""
        from trackcast.db.migrations import add_performance_indexes
        
        mock_session = Mock()
        
        with patch('trackcast.db.add_performance_indexes.upgrade', side_effect=Exception("Index creation failed")):
            result = add_performance_indexes(mock_session)
            
            # Verify error handling
            assert result['status'] == 'error'
            assert 'Index creation failed' in result['message']
            
            # Verify rollback was called
            mock_session.rollback.assert_called_once()
    
    def test_migration_order_preserves_dependencies(self):
        """Test that migrations run in the correct order to preserve dependencies."""
        from trackcast.db import migrations
        import inspect
        
        # Get the migration list from the run_migrations function
        source = inspect.getsource(migrations.run_migrations)
        
        # Verify performance migration is after table creation migrations
        assert 'add_performance_indexes' in source
        
        # Check that it comes after table structure migrations
        lines = source.split('\n')
        migration_lines = [line for line in lines if ('"add_' in line or '"create_' in line) and '",' in line]
        
        performance_line_idx = None
        table_creation_idx = None
        
        for i, line in enumerate(migration_lines):
            if 'add_performance_indexes' in line:
                performance_line_idx = i
            if 'create_train_stops_table' in line:
                table_creation_idx = i
        
        assert performance_line_idx is not None, "Performance migration should be found"
        assert table_creation_idx is not None, "Table creation migration should be found"
        assert performance_line_idx > table_creation_idx, "Performance migration should come after table creation"