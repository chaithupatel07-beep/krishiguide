# 🌾 KrishiGuide AI — Smart Farming Assistant

[![React](https://img.shields.io/badge/React-18.3+-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Lucide](https://img.shields.io/badge/Lucide-Icons-F56565?logo=feather&logoColor=white)](https://lucide.dev/)
[![Vercel](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel&logoColor=white)](https://vercel.com/)
[![Netlify](https://img.shields.io/badge/Deploy-Netlify-00C7B7?logo=netlify&logoColor=white)](https://www.netlify.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Empowering farmers with trusted, contextual agricultural intelligence, crop advisory, water conservation methods, soil fertility management, and AI-driven agronomic guidance.**

---

## 🌟 Overview

**KrishiGuide AI** is a modern, responsive web application designed for farmers, agricultural extension workers, and agronomy researchers. It bridges the gap between scientific agricultural research (ICAR, agricultural universities, and Ministry of Agriculture guidelines) and ground-level farming decisions.

Whether deployed as a standalone frontend or paired with a Retrieval-Augmented Generation (RAG) backend, KrishiGuide provides clear, actionable advice across crop lifecycles.

---

## 🚀 Key Modules & Features

### 1. 🌿 AI Farming Assistant
- Natural language query answering for farming and agronomy questions.
- Built-in multi-language selector (English, Hindi, Telugu).
- Ground-truth citation listing (`Sources` display with document and institution attribution).
- Resilient fallback knowledge engine providing verified agricultural answers even when the live backend is offline.

### 2. 🌾 Crop Advisor
- Interactive crop catalog featuring major Kharif, Rabi, and multi-season crops (Rice, Groundnut, Cotton, Red Gram, Maize, Chilli).
- Real-time search filter by crop name, soil suitability, growing duration, water needs, and season.
- Direct 1-click prompt generation to ask the AI assistant detailed management practices for any crop.

### 3. 💧 Weather & Irrigation Management
- Practical water management and micro-irrigation guidance (Drip irrigation, Rainwater harvesting, Mulching).
- Growth-stage irrigation scheduling to maximize crop water productivity.
- Heat stress mitigation and weather-informed spraying schedules.

### 4. 🧪 Soil Health & Balanced Fertilization
- Guidance on Soil Health Card testing and interpretation.
- Organic matter enhancement via farmyard manure (FYM), vermicompost, and green manuring.
- Integrated Soil Fertility Management (ISFM) to prevent soil acidification and salinity.

### 5. 📚 Knowledge Library & RAG Integration
- Curated repository structure for Packages of Practice, crop protection, and government schemes (PM-KISAN, PMKSY, PMFBY).
- Designed for seamless connection with semantic search engines, vector databases (pgvector/FAISS), and LLMs.

---

## 📁 Repository Structure

```
krishiguide/
├── frontend/                     # React + Vite Client Application
│   ├── public/                   # Static assets & favicon
│   ├── src/
│   │   ├── App.jsx               # Main KrishiGuide dashboard & modules
│   │   ├── index.css             # Harmonious styling & design system
│   │   └── main.jsx              # Application bootstrap
│   ├── .env.example              # Configurable backend API environment variables
│   ├── index.html                # HTML entry point with DM Sans & Manrope fonts
│   ├── package.json              # Frontend dependencies (React, Axios, Lucide)
│   └── vite.config.js            # Vite configuration with dev proxy
├── .gitignore                    # Git ignore rules for node_modules and build artifacts
├── netlify.toml                  # Netlify 1-click deployment configuration
├── package.json                  # Root runner script delegating to frontend
├── vercel.json                   # Vercel 1-click deployment configuration
└── README.md                     # Documentation & setup guide
```

---

## 🛠️ Quickstart & Local Setup

### Prerequisites
- **Node.js** (v18.x or later)
- **npm** (v9.x or later)

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/chaithupatel07-beep/krishiguide.git
   cd krishiguide
   ```

2. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   ```

3. **Start local development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173) in your browser.

4. **Build for production:**
   ```bash
   npm run build
   ```
   The production-ready static assets will be generated in `frontend/dist`.

---

## 🌐 1-Click Cloud Deployment

### Deploying to Vercel
1. Push your repository to GitHub (`main` branch).
2. Go to [Vercel](https://vercel.com) and click **"Add New Project"**.
3. Import `chaithupatel07-beep/krishiguide`.
4. The included [`vercel.json`](./vercel.json) automatically sets the build command (`npm --prefix frontend run build`) and output directory (`frontend/dist`).
5. Click **Deploy**!

### Deploying to Netlify
1. Go to [Netlify](https://app.netlify.com) and click **"Add new site" -> "Import an existing project"**.
2. Select `chaithupatel07-beep/krishiguide`.
3. The included [`netlify.toml`](./netlify.toml) automatically sets base directory to `frontend` and publish directory to `dist`.
4. Click **Deploy Site**!

---

## 🔌 Backend RAG API Contract

To connect your custom FastAPI or Python RAG pipeline:
1. Copy `frontend/.env.example` to `frontend/.env`:
   ```env
   VITE_API_URL=https://your-backend-api.com/api
   ```
2. Your backend should expose:
   - **Endpoint:** `POST /api/assistant/query`
   - **Request Body:**
     ```json
     {
       "question": "What is the recommended fertilizer dosage for Rice in loamy soil?",
       "language": "English"
     }
     ```
   - **Response Body:**
     ```json
     {
       "answer": "For Rice in loamy soil, apply 100:50:50 kg N:P2O5:K2O per hectare...",
       "sources": [
         "ICAR Package of Practices - Rice Cultivation Manual, Page 24",
         "Soil Health Card Guidelines"
       ]
     }
     ```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).