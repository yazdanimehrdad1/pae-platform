import { AppProviders } from "./providers";
import { AppRoutes } from "./routes";

const App = () => (
  <AppProviders>
    <AppRoutes />
  </AppProviders>
);

export default App;
