import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import ProtectedRoute from "./auth/ProtectedRoute";
import AppLayout from "./layouts/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import ModulePage from "./pages/ModulePage";

function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route
            index
            element={<DashboardPage />}
          />

          <Route
            path="accueil"
            element={
              <ModulePage
                title="Accueil"
                description="Gestion des patients, arrivées et orientation."
              />
            }
          />

          <Route
            path="hospitalisation"
            element={
              <ModulePage
                title="Hospitalisation"
                description="Admissions, chambres, lits, transferts et sorties."
              />
            }
          />

          <Route
            path="paiement"
            element={
              <ModulePage
                title="Paiement & facturation"
                description="Charges, factures, paiements et reçus."
              />
            }
          />

          <Route
            path="consultation"
            element={
              <ModulePage
                title="Consultation"
                description="Consultations médicales, diagnostics et prescriptions."
              />
            }
          />

          <Route
            path="laboratoire"
            element={
              <ModulePage
                title="Laboratoire"
                description="Demandes d'analyses, prélèvements et résultats."
              />
            }
          />

          <Route
            path="pharmacie"
            element={
              <ModulePage
                title="Pharmacie, stock & logistique"
                description="Médicaments, lots, stock et délivrances."
              />
            }
          />

          <Route
            path="maternite"
            element={
              <ModulePage
                title="Maternité"
                description="Suivi obstétrical, admission et naissance."
              />
            }
          />

          <Route
            path="rendez-vous"
            element={
              <ModulePage
                title="Rendez-vous & agenda"
                description="Rendez-vous médicaux et organisation de l'agenda."
              />
            }
          />

          <Route
            path="administration"
            element={
              <ModulePage
                title="Utilisateurs & notifications"
                description="Comptes, rôles, permissions et notifications."
              />
            }
          />

          <Route
            path="statistiques"
            element={
              <ModulePage
                title="BI & statistiques"
                description="Indicateurs, statistiques et aide à la décision."
              />
            }
          />

          <Route
            path="assistant"
            element={
              <ModulePage
                title="Assistant intelligent"
                description="Chatbot d'assistance hospitalière."
              />
            }
          />
        </Route>
      </Route>

      <Route
        path="*"
        element={<Navigate to="/" replace />}
      />
    </Routes>
  );
}

export default App;
