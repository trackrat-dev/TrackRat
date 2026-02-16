import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LandingPage } from './pages/LandingPage';
import { TripSelectionPage } from './pages/TripSelectionPage';
import { TrainListPage } from './pages/TrainListPage';
import { TrainDetailsPage } from './pages/TrainDetailsPage';
import { FavoritesPage } from './pages/FavoritesPage';

function App() {
  return (
    <BrowserRouter basename="/">
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="/departures" element={<TripSelectionPage />} />
          <Route path="/trains/:from/:to" element={<TrainListPage />} />
          <Route path="/train/:trainId/:from?/:to?" element={<TrainDetailsPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/departures" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
