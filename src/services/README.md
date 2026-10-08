# Data services

UI pages call typed services and do not access browser storage or PostgreSQL directly.
The current local adapters use the existing operational demo data and local browser
storage where persistence is needed. Replace each adapter with `apiRequest` calls
to the FastAPI service when `VITE_API_BASE_URL` is configured.

The browser must communicate only with the API. PostgreSQL credentials and database
connections belong exclusively to the future backend. Partner purchase records,
replenishment predictions, and prediction outcomes have typed contracts, but no
historical training data or ML model is present yet. The partner service therefore
reports insufficient data instead of fabricating predictions.
