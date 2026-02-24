import Foundation
@testable import TrackRat

extension Train {
    static func mock(
        id: Int = Int.random(in: 1...1000),
        trainId: String = "TR\(Int.random(in: 100...999))",
        line: String = "Mock Line",
        destination: String = "Mock Destination",
        departureTime: Date = Date(),
        track: String? = nil,
        status: TrainStatus = .onTime,
        delayMinutes: Int? = nil,
        stops: [Stop]? = [Stop.mock()],
        predictionData: PredictionData? = nil,
        originStationCode: String? = "NP",
        dataSource: String? = "NJT",
        consolidatedId: String? = nil,
        originStation: OriginStation? = nil,
        dataSources: [DataSource]? = nil,
        currentPosition: CurrentPosition? = nil,
        trackAssignment: TrackAssignment? = nil,
        statusSummary: StatusSummary? = nil,
        consolidationMetadata: ConsolidationMetadata? = nil,
        statusV2: StatusV2? = nil,
        progress: TrainProgress? = nil,
        observationType: String? = nil
    ) -> Train {
        return Train(
            id: id,
            trainId: trainId,
            line: line,
            destination: destination,
            departureTime: departureTime,
            track: track,
            status: status,
            delayMinutes: delayMinutes,
            stops: stops,
            predictionData: predictionData,
            originStationCode: originStationCode,
            dataSource: dataSource,
            consolidatedId: consolidatedId,
            originStation: originStation,
            dataSources: dataSources,
            currentPosition: currentPosition,
            trackAssignment: trackAssignment,
            statusSummary: statusSummary,
            consolidationMetadata: consolidationMetadata,
            statusV2: statusV2,
            progress: progress,
            observationType: observationType
        )
    }
}
