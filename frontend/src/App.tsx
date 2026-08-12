import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import ProtectedRoute from "./auth/ProtectedRoute";
import AppLayout from "./layouts/AppLayout";
import AccueilPage from "./pages/AccueilPage";
import DashboardPage from "./pages/DashboardPage";
import MaternityDetailPage from "./pages/MaternityDetailPage";
import MaternityPage from "./pages/MaternityPage";
import PharmacyOrderDetailPage from "./pages/PharmacyOrderDetailPage";
import PharmacyPage from "./pages/PharmacyPage";
import BillingDetailPage from "./pages/BillingDetailPage";
import BillingPage from "./pages/BillingPage";
import HospitalizationDetailPage from "./pages/HospitalizationDetailPage";
import HospitalizationPage from "./pages/HospitalizationPage";
import ConsultationDetailPage from "./pages/ConsultationDetailPage";
import ConsultationPage from "./pages/ConsultationPage";
import LoginPage from "./pages/LoginPage";
import LaboratoryDetailPage from "./pages/LaboratoryDetailPage";
import LaboratoryPage from "./pages/LaboratoryPage";
import PatientDetailPage from "./pages/PatientDetailPage";
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
            element={<AccueilPage />}
          />

          <Route
            path="accueil/patients/:patientId"
            element={<PatientDetailPage />}
          />

          <Route
            path="hospitalisation"
            element={<HospitalizationPage />}
          />

          <Route
            path="hospitalisation/:admissionId"
            element={<HospitalizationDetailPage />}
          />

          <Route
            path="paiement"
            element={<BillingPage />}
          />

          <Route
            path="paiement/:invoiceId"
            element={<BillingDetailPage />}
          />

          <Route
            path="consultation"
            element={<ConsultationPage />}
          />

          <Route
            path="consultation/:consultationId"
            element={<ConsultationDetailPage />}
          />

          <Route
            path="laboratoire"
            element={<LaboratoryPage />}
          />

          <Route
            path="laboratoire/:requestId"
            element={<LaboratoryDetailPage />}
          />

          <Route
            path="pharmacie"
            element={<PharmacyPage />}
          />

          <Route
            path="pharmacie/ordonnances/:orderId"
            element={<PharmacyOrderDetailPage />}
          />

          <Route
            path="maternite"
            element={<MaternityPage />}
          />

          <Route
            path="maternite/:caseId"
            element={<MaternityDetailPage />}
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
