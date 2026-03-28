import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { LandingPage } from './pages/LandingPage';
import { TripSelectionPage } from './pages/TripSelectionPage';
import { TrainListPage } from './pages/TrainListPage';
import { TrainDetailsPage } from './pages/TrainDetailsPage';
import { FavoritesPage } from './pages/FavoritesPage';
import { RouteStatusPage } from './pages/RouteStatusPage';
import { NetworkStatusPage } from './pages/NetworkStatusPage';

function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter basename="/">
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="/departures" element={<TripSelectionPage />} />
          <Route path="/trains/:from/:to" element={<TrainListPage />} />
          <Route path="/route/:from/:to" element={<RouteStatusPage />} />
          <Route path="/train/:trainId/:from?/:to?" element={<TrainDetailsPage />} />
          <Route path="/status" element={<NetworkStatusPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/departures" replace />} />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
