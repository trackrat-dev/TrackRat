"""
Factory functions for creating Amtrak test data.

Provides convenient functions to create test objects for Amtrak integration testing.
"""

from datetime import datetime, timedelta
from typing import Any

from trackrat.models.api import AmtrakStationData, AmtrakTrainData
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et


def create_amtrak_station_data(
    name: str = "New York Penn Station",
    code: str = "NYP",
    tz: str = "ET",
    bus: bool = False,
    sch_dep: str | None = None,
    sch_arr: str | None = None,
    actual_dep: str | None = None,
    actual_arr: str | None = None,
    status: str = "Enroute",
    platform: str = "",
    dep_cmnt: str = "",
    arr_cmnt: str = "",
) -> AmtrakStationData:
    """Factory for creating AmtrakStationData objects."""
    return AmtrakStationData(
        name=name,
        code=code,
        tz=tz,
        bus=bus,
        schDep=sch_dep,
        schArr=sch_arr,
        dep=actual_dep,
        arr=actual_arr,
        arrCmnt=arr_cmnt,
        depCmnt=dep_cmnt,
        status=status,
        stopIconColor="",
        platform=platform,
    )


def create_amtrak_train_data(
    train_num: str = "2150",
    route: str = "Acela",
    train_id: str | None = None,
    stops_at_nyp: bool = True,
    train_state: str = "Active",
    stations: list[AmtrakStationData] | None = None,
) -> AmtrakTrainData:
    """Factory for creating AmtrakTrainData objects."""
    if train_id is None:
        train_id = f"{train_num}-5"

    if stations is None:
        # Create default stations based on stops_at_nyp
        if stops_at_nyp:
            stations = [
                create_amtrak_station_data(
                    name="Boston South Station",
                    code="BOS",
                    sch_dep="2025-07-05T06:00:00-05:00",
                    status="Departed",
                ),
                create_amtrak_station_data(
                    name="New York Penn Station",
                    code="NYP",
                    sch_arr="2025-07-05T09:51:00-05:00",
                    sch_dep="2025-07-05T10:05:00-05:00",
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    name="Washington Union Station",
                    code="WAS",
                    sch_arr="2025-07-05T12:45:00-05:00",
                    status="Enroute",
                ),
            ]
        else:
            # Train that doesn't stop at NYP
            stations = [
                create_amtrak_station_data(
                    name="Boston South Station",
                    code="BOS",
                    sch_dep="2025-07-05T06:00:00-05:00",
                    status="Departed",
                ),
                create_amtrak_station_data(
                    name="Philadelphia 30th Street Station",
                    code="PHL",
                    sch_arr="2025-07-05T12:45:00-05:00",
                    status="Enroute",
                ),
            ]

    return AmtrakTrainData(
        routeName=route,
        trainNum=train_num,
        trainNumRaw=train_num,
        trainID=train_id,
        lat=40.7505,
        lon=-73.9934,
        trainTimely="0",
        iconColor="#FF0000",
        textColor="#FFFFFF",
        stations=stations,
        heading="S",
        eventCode="NYP" if stops_at_nyp else "PHL",
        eventTZ="ET",
        eventName=(
            "New York Penn Station"
            if stops_at_nyp
            else "Philadelphia 30th Street Station"
        ),
        origCode="BOS",
        originTZ="ET",
        origName="Boston South Station",
        destCode="WAS" if stops_at_nyp else "PHL",
        destTZ="ET",
        destName=(
            "Washington Union Station"
            if stops_at_nyp
            else "Philadelphia 30th Street Station"
        ),
        trainState=train_state,
        velocity=75.5,
        statusMsg="",
        createdAt="2025-07-05T10:30:00Z",
        updatedAt="2025-07-05T10:35:00Z",
        lastValTS="2025-07-05T10:35:00Z",
        objectID=12345,
        provider="Amtrak",
        providerShort="AMTK",
        onlyOfTrainNum=False,
        alerts=[],
    )


def create_amtrak_journey(
    train_id: str = "A2150",
    origin: str = "NY",
    destination: str = "Washington Union Station",
    scheduled_departure: datetime | None = None,
    data_source: str = "AMTRAK",
    line_code: str = "AM",
    line_name: str = "Amtrak",
    line_color: str = "#003366",
    is_cancelled: bool = False,
    is_completed: bool = False,
) -> TrainJourney:
    """Factory for creating Amtrak TrainJourney objects."""
    if scheduled_departure is None:
        scheduled_departure = now_et() + timedelta(hours=2)

    return TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        data_source=data_source,
        line_code=line_code,
        line_name=line_name,
        line_color=line_color,
        destination=destination,
        origin_station_code=origin,
        terminal_station_code=origin,  # Will be updated when stops are added
        scheduled_departure=scheduled_departure,
        first_seen_at=now_et(),
        last_updated_at=now_et(),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=is_cancelled,
        is_completed=is_completed,
    )


def create_amtrak_journey_stop(
    station_code: str = "NY",
    station_name: str = "New York Penn Station",
    stop_sequence: int = 0,
    scheduled_departure: datetime | None = None,
    scheduled_arrival: datetime | None = None,
    actual_departure: datetime | None = None,
    actual_arrival: datetime | None = None,
    has_departed_station: bool = False,
    raw_amtrak_status: str = "Enroute",
    track: str | None = None,
) -> JourneyStop:
    """Factory for creating JourneyStop objects for Amtrak journeys."""
    return JourneyStop(
        station_code=station_code,
        station_name=station_name,
        stop_sequence=stop_sequence,
        scheduled_departure=scheduled_departure,
        scheduled_arrival=scheduled_arrival,
        updated_departure=scheduled_departure,
        updated_arrival=scheduled_arrival,
        actual_departure=actual_departure,
        actual_arrival=actual_arrival,
        has_departed_station=has_departed_station,
        raw_amtrak_status=raw_amtrak_status,
        track=track,
    )


def create_mock_amtrak_api_response(
    train_count: int = 3,
    include_non_nyp_train: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Create a mock Amtrak API response with multiple trains."""
    response: dict[str, list[dict[str, Any]]] = {}

    # Add trains that serve NYP
    for i in range(train_count):
        train_num = str(2150 + i)
        train_data = create_amtrak_train_data(
            train_num=train_num,
            route="Acela" if i == 0 else "Northeast Regional",
            stops_at_nyp=True,
        )
        response[train_num] = [train_data.model_dump()]

    # Add a train that doesn't serve NYP (for filtering tests)
    if include_non_nyp_train:
        non_nyp_train = create_amtrak_train_data(
            train_num="350",
            route="Pennsylvanian",
            stops_at_nyp=False,
        )
        response["350"] = [non_nyp_train.model_dump()]

    return response
