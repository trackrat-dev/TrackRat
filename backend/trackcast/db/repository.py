"""
Repository pattern implementation for database access.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from trackcast.db.models import ModelData, PredictionData, Train, TrainStop

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self, session: Session):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session


class TrainRepository(BaseRepository):
    """Repository for train data operations."""

    def get_train_by_id(self, train_id: str) -> Optional[Train]:
        """
        Get the most recent train by its ID.

        Args:
            train_id: The train identifier

        Returns:
            Train object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return (
                self.session.query(Train)
                .filter(Train.train_id == train_id)
                .order_by(Train.departure_time.desc())
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_train_by_id: {str(e)}")
            raise

    def get_train_by_db_id(self, db_id: int) -> Optional[Train]:
        """
        Get a train by its database ID.

        Args:
            db_id: The database ID (primary key)

        Returns:
            Train object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return self.session.query(Train).filter(Train.id == db_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_train_by_db_id: {str(e)}")
            raise

    def get_train_by_id_and_time(self, train_id: str, departure_time: datetime) -> Optional[Train]:
        """
        Get a train by its ID and departure time.

        Args:
            train_id: The train identifier
            departure_time: The train departure time

        Returns:
            Train object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Define a small time window to account for minor time differences
            time_window = timedelta(minutes=1)
            start_time = departure_time - time_window
            end_time = departure_time + time_window

            return (
                self.session.query(Train)
                .filter(
                    Train.train_id == train_id,
                    Train.departure_time >= start_time,
                    Train.departure_time <= end_time,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_train_by_id_and_time: {str(e)}")
            raise

    def get_train_by_id_time_and_station(
        self, train_id: str, departure_time: datetime, station_code: str
    ) -> Optional[Train]:
        """
        Get a train by its ID, departure time, and origin station.

        Args:
            train_id: The train identifier
            departure_time: The train departure time
            station_code: The origin station code

        Returns:
            Train object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Define a small time window to account for minor time differences
            time_window = timedelta(minutes=1)
            start_time = departure_time - time_window
            end_time = departure_time + time_window

            return (
                self.session.query(Train)
                .filter(
                    Train.train_id == train_id,
                    Train.departure_time >= start_time,
                    Train.departure_time <= end_time,
                    Train.origin_station_code == station_code,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_train_by_id_time_and_station: {str(e)}")
            raise

    def get_train_by_id_time_and_station_source(
        self, train_id: str, departure_time: datetime, station_code: str, data_source: str
    ) -> Optional[Train]:
        """
        Get a train by its ID, departure time, origin station, and data source.

        Args:
            train_id: The train identifier
            departure_time: The train departure time
            station_code: The origin station code
            data_source: The data source (njtransit or amtrak)

        Returns:
            Train object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Define a small time window to account for minor time differences
            time_window = timedelta(minutes=1)
            start_time = departure_time - time_window
            end_time = departure_time + time_window

            return (
                self.session.query(Train)
                .filter(
                    Train.train_id == train_id,
                    Train.departure_time >= start_time,
                    Train.departure_time <= end_time,
                    Train.origin_station_code == station_code,
                    Train.data_source == data_source,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_train_by_id_time_and_station_source: {str(e)}")
            raise

    def create_train(self, train_data: Dict[str, Any], timestamp) -> Train:
        """
        Create a new train record.

        Args:
            train_data: Dict with train attributes

        Returns:
            Created Train object

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            train = Train(**train_data)
            self.session.add(train)
            self.session.commit()
            logger.info(f"Created train {train.train_id} departing at {train.departure_time}")
            return train
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in create_train: {str(e)}")
            raise

    def update_train(self, train: Train, update_data: Dict[str, Any], timestamp) -> Train:
        """
        Update an existing train record.

        Args:
            train: Train object to update
            update_data: Dict with attributes to update

        Returns:
            Updated Train object

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Track old values for logging
            old_track = train.track
            old_status = train.status

            # Apply all updates
            for key, value in update_data.items():
                if value:
                    setattr(train, key, value)

            # Handle track assignment
            if "track" in update_data and update_data["track"] and not train.track_assigned_at:
                if update_data["track"] != old_track:
                    train.track_assigned_at = timestamp
                    logger.info(f"Track {update_data['track']} assigned to train {train.train_id} at %s" % timestamp)

            # Calculate delay_minutes when track_released_at is set (train has departed)
            # Use "not train.delay_minutes and train.track_released_at" to identify trains needing delay calculation
            # WARNING: track_released_at is only valid when status=DEPARTED (see "Handle train departure" section below)
            if not train.delay_minutes and train.track_released_at and train.status == "DEPARTED":
                # Calculate delay as the difference between scheduled and actual departure
                scheduled_time = train.departure_time
                departure_time = train.track_released_at
                # Calculate delay in minutes (can be negative if early)
                delay_in_minutes = int((departure_time - scheduled_time).total_seconds() // 60)

                # Only set delay_minutes if there's an actual delay (> 0 minutes)
                if delay_in_minutes > 0:
                    train.delay_minutes = delay_in_minutes
                    logger.info(f"Calculated delay of {delay_in_minutes} minutes for train {train.train_id}")
                else:
                    # No delay or early departure
                    train.delay_minutes = 0
                    logger.info(f"Train {train.train_id} departed on time or early")

            # Handle train departure
            # because we can't presume we will be called when a train has departed (sometimes if we don't check fast enough
            # it will just drop off the train list before we see it switch to DEPARTED) we always keep track_released_at set
            # to the latest value
            if old_status != "DEPARTED":
                train.track_released_at = timestamp

            self.session.commit()
            return train
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in update_train: {str(e)}")
            raise

    def get_trains(
        self,
        train_id: Optional[str] = None,
        line: Optional[str] = None,
        destination: Optional[str] = None,
        departure_time_after: Optional[datetime] = None,
        departure_time_before: Optional[datetime] = None,
        track: Optional[str] = None,
        status: Optional[str] = None,
        has_prediction: Optional[bool] = None,
        has_track: Optional[bool] = None,
        train_split: Optional[str] = None,
        exclude_train_split: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: Optional[int] = 20,
        offset: int = 0,
        stops_at_station: Optional[str] = None,
        stops_at_station_code: Optional[str] = None,
        stops_at_station_name: Optional[str] = None,
        origin_station_code: Optional[str] = None,
        origin_station_name: Optional[str] = None,
        from_station_code: Optional[str] = None,
        to_station_code: Optional[str] = None,
        data_source: Optional[str] = None,
    ) -> Tuple[List[Train], int]:
        """
        Get trains with optional filtering and sorting.

        Args:
            train_id: Filter by train ID
            line: Filter by train line
            destination: Filter by destination
            departure_time_after: Filter by departure time after
            departure_time_before: Filter by departure time before
            track: Filter by track number
            status: Filter by status
            has_prediction: Filter by presence of prediction
            has_track: Filter to only include trains with assigned tracks
            train_split: Filter by data split (train, validation, test)
            exclude_train_split: Exclude trains with this data split value
            sort_by: Field to sort by (e.g., "departure_time", "line", "destination")
            sort_order: Sort direction, either "asc" or "desc"
            limit: Number of results to return
            offset: Offset for pagination
            stops_at_station: Filter trains that stop at this station (searches both code and name)
            stops_at_station_code: Filter trains that stop at this station code exactly
            stops_at_station_name: Filter trains that stop at this station name (partial match)
            origin_station_code: Filter by origin station code
            origin_station_name: Filter by origin station name (partial match)
            from_station_code: Filter trains that stop at this station code (boarding station)
            to_station_code: Filter trains that stop at this station code after from_station_code (alighting station)
            data_source: Filter by data source ('njtransit' or 'amtrak')

        Returns:
            Tuple containing:
            - List of Train objects
            - Total count of matching trains

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Build base query - if filtering by stops, we need to join with train_stops
            if (stops_at_station or stops_at_station_code or stops_at_station_name or 
                from_station_code or to_station_code):
                query = self.session.query(Train).join(
                    TrainStop,
                    and_(
                        Train.train_id == TrainStop.train_id,
                        Train.departure_time == TrainStop.train_departure_time
                    )
                ).distinct()
            else:
                query = self.session.query(Train)

            # Apply filters
            if train_id:
                query = query.filter(Train.train_id == train_id)
            if line:
                query = query.filter(Train.line == line)
            if destination:
                query = query.filter(Train.destination == destination)
            # Apply departure time filters (will be overridden if using from/to station filtering)
            if departure_time_after and not (from_station_code and to_station_code):
                query = query.filter(Train.departure_time >= departure_time_after)
            if departure_time_before and not (from_station_code and to_station_code):
                query = query.filter(Train.departure_time <= departure_time_before)
            if track:
                query = query.filter(Train.track == track)
            if status:
                query = query.filter(Train.status == status)
            if has_prediction is not None:
                if has_prediction:
                    query = query.filter(Train.prediction_data_id != None)
                else:
                    query = query.filter(Train.prediction_data_id == None)
            if has_track is not None:
                if has_track:
                    query = query.filter(Train.track != None, Train.track != "")
                else:
                    query = query.filter(or_(Train.track == None, Train.track == ""))
            if train_split:
                query = query.filter(Train.train_split == train_split)
            if exclude_train_split:
                query = query.filter(or_(Train.train_split != exclude_train_split, Train.train_split == None))
            
            # Apply origin station filters
            if origin_station_code:
                query = query.filter(Train.origin_station_code == origin_station_code)
            if origin_station_name:
                query = query.filter(Train.origin_station_name.ilike(f"%{origin_station_name}%"))
            
            # Apply data source filter
            if data_source:
                query = query.filter(Train.data_source == data_source)
            
            # Apply stop-based filters (only include future stops where departed=False)
            if stops_at_station:
                # Search both station code and station name, but only future stops
                query = query.filter(
                    and_(
                        TrainStop.departed == False,
                        or_(
                            TrainStop.station_code == stops_at_station,
                            TrainStop.station_name.ilike(f"%{stops_at_station}%")
                        )
                    )
                )
            elif stops_at_station_code:
                # Exact station code match, but only future stops
                query = query.filter(
                    and_(
                        TrainStop.departed == False,
                        TrainStop.station_code == stops_at_station_code
                    )
                )
            elif stops_at_station_name:
                # Station name partial match, but only future stops
                query = query.filter(
                    and_(
                        TrainStop.departed == False,
                        TrainStop.station_name.ilike(f"%{stops_at_station_name}%")
                    )
                )

            # Apply from/to station filtering (both must be provided)
            if from_station_code and to_station_code:
                if from_station_code == to_station_code:
                    # Same station for from and to doesn't make sense
                    return [], 0
                
                # Create aliases for the train_stops table to do self-join
                from sqlalchemy.orm import aliased
                from_stop = aliased(TrainStop)
                to_stop = aliased(TrainStop)
                
                # Re-build query with explicit joins for from/to stations
                query = self.session.query(Train).join(
                    from_stop,
                    and_(
                        Train.train_id == from_stop.train_id,
                        Train.departure_time == from_stop.train_departure_time,
                        from_stop.station_code == from_station_code
                    )
                ).join(
                    to_stop,
                    and_(
                        Train.train_id == to_stop.train_id,
                        Train.departure_time == to_stop.train_departure_time,
                        to_stop.station_code == to_station_code,
                        # Ensure from_stop happens before to_stop
                        from_stop.scheduled_time < to_stop.scheduled_time
                    )
                ).distinct()
                
                # Re-apply all the previous filters since we rebuilt the query
                if train_id:
                    query = query.filter(Train.train_id == train_id)
                if line:
                    query = query.filter(Train.line == line)
                if destination:
                    query = query.filter(Train.destination == destination)
                # When using from/to station filtering, filter departure times based on from_station
                if departure_time_after:
                    query = query.filter(from_stop.scheduled_time >= departure_time_after)
                if departure_time_before:
                    query = query.filter(from_stop.scheduled_time <= departure_time_before)
                if track:
                    query = query.filter(Train.track == track)
                if status:
                    query = query.filter(Train.status == status)
                if has_prediction is not None:
                    if has_prediction:
                        query = query.filter(Train.prediction_data_id != None)
                    else:
                        query = query.filter(Train.prediction_data_id == None)
                if has_track is not None:
                    if has_track:
                        query = query.filter(Train.track != None, Train.track != "")
                    else:
                        query = query.filter(or_(Train.track == None, Train.track == ""))
                if train_split:
                    query = query.filter(Train.train_split == train_split)
                if exclude_train_split:
                    query = query.filter(or_(Train.train_split != exclude_train_split, Train.train_split == None))
                if origin_station_code:
                    query = query.filter(Train.origin_station_code == origin_station_code)
                if origin_station_name:
                    query = query.filter(Train.origin_station_name.ilike(f"%{origin_station_name}%"))
                if data_source:
                    query = query.filter(Train.data_source == data_source)

            # Get total count for pagination
            total_count = query.count()

            # Define a dictionary of valid sort fields mapping to their corresponding model attributes
            valid_sort_fields = {
                "train_id": Train.train_id,
                "line": Train.line,
                "destination": Train.destination,
                "departure_time": Train.departure_time,
                "status": Train.status,
                "track": Train.track,
                "track_assigned_at": Train.track_assigned_at,
                "delay_minutes": Train.delay_minutes,
                "created_at": Train.created_at,
                "origin_station_code": Train.origin_station_code,
                "origin_station_name": Train.origin_station_name,
            }

            # Apply ordering based on sort_by and sort_order if provided
            if sort_by and sort_by in valid_sort_fields:
                sort_field = valid_sort_fields[sort_by]
                # Apply the sort order
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_field.desc())
                else:
                    query = query.order_by(sort_field.asc())
            else:
                # Default ordering if no sort_by provided or invalid field
                query = query.order_by(Train.departure_time.asc())

            # Apply pagination if limit is specified
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            trains = query.all()

            return trains, total_count

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_trains: {str(e)}")
            raise

    def get_trains_for_time_range(self, start_time: datetime, end_time: datetime) -> List[Train]:
        """
        Get all trains within a time range.

        Args:
            start_time: Starting time range
            end_time: Ending time range

        Returns:
            List of Train objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return (
                self.session.query(Train)
                .filter(Train.departure_time >= start_time, Train.departure_time <= end_time)
                .order_by(Train.departure_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_trains_for_time_range: {str(e)}")
            raise

    def get_recent_trains(self, hours: int = 24) -> List[Train]:
        """
        Get trains from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of Train objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return (
                self.session.query(Train)
                .filter(Train.departure_time >= cutoff_time)
                .order_by(Train.departure_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_recent_trains: {str(e)}")
            raise

    def get_trains_for_collection(self) -> List[Train]:
        """
        Get trains that need updated data from the API.
        This includes:
        - Trains departing in the next 4 hours
        - Trains that departed in the last 30 minutes
        - Trains with no track assigned

        Returns:
            List of Train objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            now = datetime.utcnow()
            four_hours_ahead = now + timedelta(hours=4)
            thirty_minutes_ago = now - timedelta(minutes=30)

            return (
                self.session.query(Train)
                .filter(
                    or_(
                        # Upcoming trains
                        and_(Train.departure_time >= now, Train.departure_time <= four_hours_ahead),
                        # Recent trains without track or status
                        and_(
                            Train.departure_time >= thirty_minutes_ago,
                            Train.departure_time <= now,
                            or_(
                                or_(Train.track == None, Train.track == ""),  # No track assigned
                                Train.status != "DEPARTED"  # Or not departed
                            ),
                        ),
                    )
                )
                .order_by(Train.departure_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_trains_for_collection: {str(e)}")
            raise

    def get_trains_needing_features(self) -> List[Train]:
        """
        Get trains that need feature engineering.
        This includes trains with no model_data relation.

        Returns:
            List of Train objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return (
                self.session.query(Train)
                .filter(Train.model_data_id == None)
                .order_by(Train.departure_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_trains_needing_features: {str(e)}")
            raise

    def get_trains_needing_predictions(self) -> List[Train]:
        """
        Get trains that need predictions.
        This includes trains with features but no predictions.

        Returns:
            List of Train objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Trains with features but no predictions
            return (
                self.session.query(Train)
                .filter(
                    Train.model_data_id != None,
                    Train.prediction_data_id == None,
                    #or_(Train.track == None, Train.track == ''),  # Only predict for trains without a track
                    #Train.departure_time >= datetime.utcnow(),  # Only future trains
                )
                .order_by(Train.departure_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_trains_needing_predictions: {str(e)}")
            raise

    def get_all_lines_and_destinations(self) -> Dict[str, List[str]]:
        """
        Get all unique lines and destinations.

        Returns:
            Dict with "lines" and "destinations" lists

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            lines = [r[0] for r in self.session.query(Train.line).distinct().all()]
            destinations = [r[0] for r in self.session.query(Train.destination).distinct().all()]
            return {"lines": lines, "destinations": destinations}
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_all_lines_and_destinations: {str(e)}")
            raise

    def clear_all_features(self) -> Dict[str, int]:
        """
        Clear model_data_id for all trains and delete orphaned model_data records.

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Get count of all model_data records before clearing
            model_data_before = self.session.query(ModelData).count()

            # Get count of trains with features
            trains_with_features = self.session.query(Train).filter(Train.model_data_id != None).count()

            # Get all model_data_ids to delete directly
            model_data_ids = [id for (id,) in self.session.query(ModelData.id).all()]

            # Clear model_data_id from all trains
            trains_updated = self.session.query(Train).filter(Train.model_data_id != None).update(
                {"model_data_id": None}, synchronize_session=False
            )

            # Delete all model_data records
            if model_data_ids:
                deleted = self.session.query(ModelData).filter(ModelData.id.in_(model_data_ids)).delete(
                    synchronize_session=False
                )
            else:
                deleted = 0

            # Commit the transaction
            self.session.commit()

            # Calculate statistics
            stats = {
                "trains_cleared": trains_updated,
                "features_deleted": deleted,
                "trains_with_features_before": trains_with_features,
                "model_data_records_before": model_data_before,
                "model_data_records_after": 0,
            }

            logger.info(f"Cleared features for {stats['trains_cleared']} trains, "
                       f"deleted {stats['features_deleted']} feature records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_all_features: {str(e)}")
            raise

    def clear_features_for_train(self, train_id: str) -> Dict[str, int]:
        """
        Clear model_data_id for a specific train and delete orphaned model_data records.

        Args:
            train_id: The train identifier

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Find trains matching this train_id
            trains = self.session.query(Train).filter(Train.train_id == train_id).all()

            if not trains:
                logger.info(f"No trains found with train_id {train_id}")
                return {"trains_cleared": 0, "features_deleted": 0}

            # Collect model_data_ids to delete
            model_data_ids = [train.model_data_id for train in trains if train.model_data_id is not None]

            # Clear model_data_id from matching trains
            trains_updated = self.session.query(Train).filter(
                Train.train_id == train_id,
                Train.model_data_id != None
            ).update({"model_data_id": None}, synchronize_session=False)

            # Delete model_data records directly
            if model_data_ids:
                deleted = self.session.query(ModelData).filter(ModelData.id.in_(model_data_ids)).delete(
                    synchronize_session=False
                )
            else:
                deleted = 0

            # Commit the transaction
            self.session.commit()

            stats = {
                "trains_cleared": trains_updated,
                "features_deleted": deleted,
            }

            logger.info(f"Cleared features for {stats['trains_cleared']} trains with ID {train_id}, "
                       f"deleted {stats['features_deleted']} feature records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_features_for_train: {str(e)}")
            raise

    def clear_features_for_time_range(self, start_time: datetime, end_time: datetime) -> Dict[str, int]:
        """
        Clear model_data_id for trains in a time range and delete orphaned model_data records.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Find trains in the time range
            trains = self.session.query(Train).filter(
                Train.departure_time >= start_time,
                Train.departure_time <= end_time,
                Train.model_data_id != None
            ).all()

            if not trains:
                logger.info(f"No trains found in time range with features")
                return {"trains_cleared": 0, "features_deleted": 0}

            # Collect model_data_ids to delete
            model_data_ids = [train.model_data_id for train in trains if train.model_data_id is not None]

            # Clear model_data_id from matching trains
            trains_updated = self.session.query(Train).filter(
                Train.departure_time >= start_time,
                Train.departure_time <= end_time,
                Train.model_data_id != None
            ).update({"model_data_id": None}, synchronize_session=False)

            # Delete model_data records directly
            if model_data_ids:
                deleted = self.session.query(ModelData).filter(ModelData.id.in_(model_data_ids)).delete(
                    synchronize_session=False
                )
            else:
                deleted = 0

            # Commit the transaction
            self.session.commit()

            stats = {
                "trains_cleared": trains_updated,
                "features_deleted": deleted,
                "time_range": f"{start_time} to {end_time}",
            }

            logger.info(f"Cleared features for {stats['trains_cleared']} trains in range {start_time} to {end_time}, "
                       f"deleted {stats['features_deleted']} feature records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_features_for_time_range: {str(e)}")
            raise

    def clear_predictions_for_time_range(self, start_time: datetime, end_time: datetime) -> Dict[str, int]:
        """
        Clear prediction_data_id for trains in a time range and delete orphaned prediction_data records.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Find trains in the time range with predictions
            trains = self.session.query(Train).filter(
                Train.departure_time >= start_time,
                Train.departure_time <= end_time,
                Train.prediction_data_id != None
            ).all()

            if not trains:
                logger.info(f"No trains found in time range with predictions")
                return {"trains_cleared": 0, "predictions_deleted": 0}

            # Collect prediction_data_ids to delete
            prediction_data_ids = [train.prediction_data_id for train in trains if train.prediction_data_id is not None]

            # Clear prediction_data_id from matching trains
            trains_updated = self.session.query(Train).filter(
                Train.departure_time >= start_time,
                Train.departure_time <= end_time,
                Train.prediction_data_id != None
            ).update({"prediction_data_id": None}, synchronize_session=False)

            # Delete prediction_data records directly
            if prediction_data_ids:
                deleted = self.session.query(PredictionData).filter(PredictionData.id.in_(prediction_data_ids)).delete(
                    synchronize_session=False
                )
            else:
                deleted = 0

            # Commit the transaction
            self.session.commit()

            stats = {
                "trains_cleared": trains_updated,
                "predictions_deleted": deleted,
                "time_range": f"{start_time} to {end_time}",
            }

            logger.info(f"Cleared predictions for {stats['trains_cleared']} trains in range {start_time} to {end_time}, "
                       f"deleted {stats['predictions_deleted']} prediction records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_predictions_for_time_range: {str(e)}")
            raise

    def clear_all_predictions(self) -> Dict[str, int]:
        """
        Clear all prediction_data_id for all trains and delete all prediction_data records.

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Get count of all prediction_data records before clearing
            prediction_data_before = self.session.query(PredictionData).count()

            # Get count of trains with predictions
            trains_with_predictions = self.session.query(Train).filter(Train.prediction_data_id != None).count()

            # Get all prediction_data_ids to delete directly
            prediction_data_ids = [id for (id,) in self.session.query(PredictionData.id).all()]

            # Clear prediction_data_id from all trains
            trains_updated = self.session.query(Train).filter(Train.prediction_data_id != None).update(
                {"prediction_data_id": None}, synchronize_session=False
            )

            # Delete all prediction_data records
            if prediction_data_ids:
                deleted = self.session.query(PredictionData).filter(PredictionData.id.in_(prediction_data_ids)).delete(
                    synchronize_session=False
                )
            else:
                deleted = 0

            # Commit the transaction
            self.session.commit()

            # Calculate statistics
            stats = {
                "trains_cleared": trains_updated,
                "predictions_deleted": deleted,
                "trains_with_predictions_before": trains_with_predictions,
                "prediction_data_records_before": prediction_data_before,
                "prediction_data_records_after": 0,
            }

            logger.info(f"Cleared predictions for {stats['trains_cleared']} trains, "
                       f"deleted {stats['predictions_deleted']} prediction records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_all_predictions: {str(e)}")
            raise

    def clear_all_train_data(self) -> Dict[str, int]:
        """
        Clear all trains and their related model_data and prediction_data records.

        Returns:
            Dictionary with statistics about the clearing operation

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Start a transaction
            self.session.begin_nested()

            # Get counts before clearing
            train_count = self.session.query(Train).count()
            model_data_count = self.session.query(ModelData).count()
            prediction_data_count = self.session.query(PredictionData).count()

            # Delete all prediction data
            prediction_deleted = self.session.query(PredictionData).delete(synchronize_session=False)

            # Delete all model data
            model_deleted = self.session.query(ModelData).delete(synchronize_session=False)

            # Delete all train data
            train_deleted = self.session.query(Train).delete(synchronize_session=False)

            # Commit the transaction
            self.session.commit()

            # Return statistics
            stats = {
                "trains_deleted": train_deleted,
                "model_data_deleted": model_deleted,
                "prediction_data_deleted": prediction_deleted,
                "trains_before": train_count,
                "model_data_before": model_data_count,
                "prediction_data_before": prediction_data_count,
            }

            logger.info(f"Cleared {stats['trains_deleted']} trains, "
                       f"{stats['model_data_deleted']} model records, "
                       f"{stats['prediction_data_deleted']} prediction records")

            return stats

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in clear_all_train_data: {str(e)}")
            raise

    def get_track_usage_history(self, hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get track usage history for the past N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dict mapping track numbers to lists of usage periods

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Get all trains with tracks assigned in the time period
            trains = (
                self.session.query(Train)
                .filter(Train.track_assigned_at >= cutoff_time)
                .order_by(Train.track_assigned_at.asc())
                .all()
            )

            track_usage = {}

            for train in trains:
                if not train.track or not train.track_assigned_at:
                    continue

                if train.track not in track_usage:
                    track_usage[train.track] = []

                usage_period = {
                    "train_id": train.train_id,
                    "line": train.line,
                    "destination": train.destination,
                    "assigned_at": train.track_assigned_at,
                    "released_at": train.track_released_at or datetime.utcnow(),
                }

                track_usage[train.track].append(usage_period)

            return track_usage

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_track_usage_history: {str(e)}")
            raise


class ModelDataRepository(BaseRepository):
    """Repository for model feature data operations."""

    def create_model_data(self, model_data: Dict[str, Any]) -> ModelData:
        """
        Create a new model data record.

        Args:
            model_data: Dict with model data attributes

        Returns:
            Created ModelData object

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            model_data_obj = ModelData(**model_data)
            self.session.add(model_data_obj)
            self.session.commit()
            logger.info(f"Created model data with ID {model_data_obj.id}")
            return model_data_obj
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in create_model_data: {str(e)}")
            raise

    def get_model_data_for_train(self, train_id: int) -> Optional[ModelData]:
        """
        Get model data for a specific train.

        Args:
            train_id: Database ID of the train

        Returns:
            ModelData object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return self.session.query(ModelData).join(Train).filter(Train.id == train_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_model_data_for_train: {str(e)}")
            raise

    def get_all_model_data(self, limit: int = 1000) -> List[ModelData]:
        """
        Get all model data records (with limit).

        Args:
            limit: Maximum number of records to return

        Returns:
            List of ModelData objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return self.session.query(ModelData).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_all_model_data: {str(e)}")
            raise


class PredictionDataRepository(BaseRepository):
    """Repository for prediction data operations."""

    def create_prediction(self, prediction_data: Dict[str, Any]) -> PredictionData:
        """
        Create a new prediction data record.

        Args:
            prediction_data: Dict with prediction data attributes

        Returns:
            Created PredictionData object

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            prediction = PredictionData(**prediction_data)
            self.session.add(prediction)
            self.session.commit()
            logger.info(f"Created prediction data with ID {prediction.id}")
            return prediction
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in create_prediction: {str(e)}")
            raise

    def get_prediction_for_train(self, train_id: int) -> Optional[PredictionData]:
        """
        Get prediction data for a specific train.

        Args:
            train_id: Database ID of the train

        Returns:
            PredictionData object or None if not found

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return (
                self.session.query(PredictionData).join(Train).filter(Train.id == train_id).first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_prediction_for_train: {str(e)}")
            raise

    def get_prediction_accuracy_stats(self) -> Dict[str, Any]:
        """
        Get prediction accuracy statistics.

        Returns:
            Dict with accuracy metrics

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Find trains with both predictions and actual track assignments
            trains_with_both = (
                self.session.query(Train)
                .filter(Train.prediction_data_id != None, Train.track != None)
                .all()
            )

            total = len(trains_with_both)
            correct = 0
            by_line = {}

            for train in trains_with_both:
                if not train.prediction_data:
                    continue

                # Get top predicted track
                predicted_track = train.prediction_data.top_track
                actual_track = train.track

                # Track accuracy
                is_correct = predicted_track == actual_track
                if is_correct:
                    correct += 1

                # Track by line
                if train.line not in by_line:
                    by_line[train.line] = {"total": 0, "correct": 0}

                by_line[train.line]["total"] += 1
                if is_correct:
                    by_line[train.line]["correct"] += 1

            # Calculate overall accuracy
            accuracy = correct / total if total > 0 else 0

            # Calculate accuracy by line
            for line in by_line:
                by_line[line]["accuracy"] = (
                    by_line[line]["correct"] / by_line[line]["total"]
                    if by_line[line]["total"] > 0
                    else 0
                )

            return {
                "total_predictions": total,
                "correct_predictions": correct,
                "accuracy": accuracy,
                "by_line": by_line,
            }

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_prediction_accuracy_stats: {str(e)}")
            raise


class TrainStopRepository(BaseRepository):
    """Repository for train stop data operations."""

    def create_train_stop(self, stop_data: Dict[str, Any]) -> TrainStop:
        """
        Create a new train stop record.

        Args:
            stop_data: Dict with train stop attributes

        Returns:
            Created TrainStop object

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            train_stop = TrainStop(**stop_data)
            self.session.add(train_stop)
            self.session.commit()
            logger.debug(f"Created train stop for train {train_stop.train_id} at {train_stop.station_name}")
            return train_stop
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in create_train_stop: {str(e)}")
            raise

    def upsert_train_stops(self, train_id: str, train_departure_time: datetime, stops_data: List[Dict[str, Any]], data_source: str = "njtransit") -> List[TrainStop]:
        """
        Create or update train stops for a specific train.

        Args:
            train_id: Train identifier
            train_departure_time: Train departure time
            stops_data: List of stop data dictionaries
            data_source: Data source identifier (njtransit or amtrak)

        Returns:
            List of created/updated TrainStop objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Import StationMapper here to avoid circular imports
            from trackcast.services.station_mapping import StationMapper
            station_mapper = StationMapper()
            
            # Delete existing stops for this train and data source
            self.session.query(TrainStop).filter(
                TrainStop.train_id == train_id,
                TrainStop.train_departure_time == train_departure_time,
                TrainStop.data_source == data_source
            ).delete(synchronize_session=False)

            # Create new stops
            train_stops = []
            for stop_data in stops_data:
                stop_data["train_id"] = train_id
                stop_data["train_departure_time"] = train_departure_time
                stop_data["data_source"] = data_source
                
                # If station_code is missing, try to derive it from station_name
                if not stop_data.get("station_code") and stop_data.get("station_name"):
                    derived_code = station_mapper.get_code_for_name(stop_data["station_name"])
                    if derived_code:
                        stop_data["station_code"] = derived_code
                        logger.debug(f"Derived station code '{derived_code}' for station name '{stop_data['station_name']}'")
                
                train_stop = TrainStop(**stop_data)
                self.session.add(train_stop)
                train_stops.append(train_stop)

            self.session.commit()
            logger.debug(f"Created {len(train_stops)} stops for train {train_id}")
            return train_stops

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in upsert_train_stops: {str(e)}")
            raise

    def get_stops_for_train(self, train_id: str, train_departure_time: datetime) -> List[TrainStop]:
        """
        Get all stops for a specific train.

        Args:
            train_id: Train identifier
            train_departure_time: Train departure time

        Returns:
            List of TrainStop objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            return (
                self.session.query(TrainStop)
                .filter(
                    TrainStop.train_id == train_id,
                    TrainStop.train_departure_time == train_departure_time
                )
                .order_by(TrainStop.scheduled_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_stops_for_train: {str(e)}")
            raise

    def get_stops_by_station(self, station_code: str, hours: int = 24) -> List[TrainStop]:
        """
        Get all stops at a specific station within a time range.

        Args:
            station_code: Station code to filter by
            hours: Number of hours to look back

        Returns:
            List of TrainStop objects

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return (
                self.session.query(TrainStop)
                .filter(
                    TrainStop.station_code == station_code,
                    TrainStop.scheduled_time >= cutoff_time
                )
                .order_by(TrainStop.scheduled_time.asc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_stops_by_station: {str(e)}")
            raise

    def get_all_stations(self) -> List[Dict[str, str]]:
        """
        Get all unique stations from the train_stops table.

        Returns:
            List of dictionaries with station information

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            # Get distinct stations, preferring entries with station codes
            results = self.session.query(
                TrainStop.station_code,
                TrainStop.station_name
            ).distinct().order_by(
                TrainStop.station_code.nulls_last(),
                TrainStop.station_name
            ).all()

            stations = []
            seen_names = set()
            
            for station_code, station_name in results:
                # Avoid duplicates by station name (some might have codes, some might not)
                if station_name not in seen_names:
                    stations.append({
                        "station_code": station_code,
                        "station_name": station_name
                    })
                    seen_names.add(station_name)
            
            return stations
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_all_stations: {str(e)}")
            raise

    def search_stations(self, query: str) -> List[Dict[str, str]]:
        """
        Search stations by name or code.

        Args:
            query: Search query string

        Returns:
            List of matching stations

        Raises:
            SQLAlchemyError: Database error
        """
        try:
            results = self.session.query(
                TrainStop.station_code,
                TrainStop.station_name
            ).filter(
                or_(
                    TrainStop.station_code.ilike(f"%{query}%"),
                    TrainStop.station_name.ilike(f"%{query}%")
                )
            ).distinct().order_by(
                TrainStop.station_code.nulls_last(),
                TrainStop.station_name
            ).limit(20).all()

            stations = []
            seen_names = set()
            
            for station_code, station_name in results:
                if station_name not in seen_names:
                    stations.append({
                        "station_code": station_code,
                        "station_name": station_name
                    })
                    seen_names.add(station_name)
            
            return stations
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in search_stations: {str(e)}")
            raise
