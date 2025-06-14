import Foundation

protocol APIServiceProtocol {
    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [Train]
    func fetchTrainDetailsFlexible(id: String?, trainId: String?, fromStationCode: String?) async throws -> Train
    func fetchTrainDetails(id: String, fromStationCode: String?) async throws -> Train
    func fetchTrainByTrainId(_ trainId: String, sinceHoursAgo: Int, consolidate: Bool) async throws -> [Train]
    func fetchHistoricalData(for train: Train, fromStationCode: String, toStationCode: String) async throws -> HistoricalData
}
