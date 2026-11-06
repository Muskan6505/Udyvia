# Udyvia frontend

Next.js 14 (App Router), Tailwind, framer-motion. The browser calls `/api/*`; Next forwards it to the FastAPI backend
(`BACKEND_URL`, default `http://127.0.0.1:8000`), so no CORS setup is needed in development.

    npm install
    npm run dev          # http://localhost:3000   (start the backend first: uvicorn app.main:app --port 8000)

Flow: welcome (language) -> advisor chat -> quote with add-on toggles -> consent -> KYC upload and check -> e-sign and pay -> tracker.
The "Demo documents" panel on the KYC screen loads the K01-K12 specimen sets, and the tracker has a "skip ahead" button.
Both are demo-only helpers.
