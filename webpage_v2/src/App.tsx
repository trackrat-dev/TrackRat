import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { TripSelectionPage } from './pages/TripSelectionPage';
import { TrainListPage } from './pages/TrainListPage';
import { TrainDetailsPage } from './pages/TrainDetailsPage';
import { FavoritesPage } from './pages/FavoritesPage';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<TripSelectionPage />} />
          <Route path="/trains/:from/:to" element={<TrainListPage />} />
          <Route path="/train/:trainId" element={<TrainDetailsPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
