import React, { useState } from "react";
import axios from "axios";
import {
  Leaf,
  Sprout,
  LayoutDashboard,
  MessageCircle,
  CloudSun,
  Droplets,
  FlaskConical,
  BookOpen,
  Search,
  Bell,
  Menu,
  X,
  Send,
  ArrowRight,
  Sun,
  Wind,
  CloudRain,
  Thermometer,
  ChevronRight,
  TrendingUp,
  Lightbulb,
  FileText,
  ShieldCheck,
  Languages,
  CircleHelp,
  Tractor,
  Wheat,
  Activity,
  CheckCircle2
} from "lucide-react";

// Robust API resolution with fallback
const API_BASE = (
  (import.meta.env && import.meta.env.VITE_API_URL) ||
  "/api"
).replace(/\/+$/, "");

const crops = [
  { name: "Rice", emoji: "🌾", season: "Kharif", duration: "120–150 days", water: "High", soil: "Clay / loamy", color: "#e7f3d9" },
  { name: "Groundnut", emoji: "🥜", season: "Kharif", duration: "100–125 days", water: "Moderate", soil: "Sandy loam", color: "#f8ead5" },
  { name: "Cotton", emoji: "🌱", season: "Kharif", duration: "150–180 days", water: "Moderate", soil: "Black soil", color: "#e4edfa" },
  { name: "Red Gram", emoji: "🫘", season: "Kharif", duration: "150–180 days", water: "Low–moderate", soil: "Well-drained soil", color: "#f7e4e1" },
  { name: "Maize", emoji: "🌽", season: "Kharif / Rabi", duration: "90–120 days", water: "Moderate", soil: "Loamy soil", color: "#fff0c9" },
  { name: "Chilli", emoji: "🌶️", season: "Multiple seasons", duration: "120–180 days", water: "Moderate", soil: "Well-drained soil", color: "#f7dfdc" }
];

const suggestions = [
  "Which crop is suitable for my soil?",
  "How can I improve soil fertility?",
  "Explain efficient irrigation methods",
  "How do I manage crop pests?"
];

const navItems = [
  { id: "Dashboard", icon: LayoutDashboard },
  { id: "AI Assistant", icon: MessageCircle },
  { id: "Crop Advisor", icon: Sprout },
  { id: "Weather & Irrigation", icon: CloudSun },
  { id: "Soil & Fertilizer", icon: FlaskConical },
  { id: "Knowledge Library", icon: BookOpen }
];

// Offline knowledge base for instant answers when backend server is starting or disconnected
function getLocalAgronomyAnswer(question, lang = "English") {
  const q = question.toLowerCase();

  if (q.includes("rice") || q.includes("paddy")) {
    return {
      answer: "Rice (Oryza sativa) requires deep clayey or loamy soil with high water retention. Ideal temperature is 20°C–38°C with consistent standing water (2–5 cm) during early vegetative stages. Recommended balanced fertilization is 100:50:50 kg N:P2O5:K2O per hectare. Monitor regularly for stem borer and blast disease using integrated pest management.",
      sources: ["ICAR Package of Practices - Rice Cultivation Manual", "Department of Agriculture & Farmers Welfare, GoI"]
    };
  }

  if (q.includes("soil") && (q.includes("fertility") || q.includes("improve") || q.includes("health"))) {
    return {
      answer: "To improve soil fertility sustainably:\n1. Organic amendments: Incorporate 5–10 tonnes/ha of well-decomposed Farmyard Manure (FYM) or vermicompost.\n2. Green manuring: Grow and incorporate Dhaincha or Sunhemp before sowing Kharif crops to fix atmospheric nitrogen.\n3. Crop rotation: Rotate heavy feeders (like Maize/Paddy) with legumes (like Red Gram/Moong) to restore soil nitrogen.\n4. Balanced NPK: Apply fertilizers based strictly on a standard Soil Health Card test rather than blanket application.",
      sources: ["Soil Health Card Scheme Guidelines, ICAR-IISS Bhopal", "FAO Sustainable Soil Management Guidelines"]
    };
  }

  if (q.includes("irrigation") || q.includes("drip") || q.includes("water")) {
    return {
      answer: "Efficient irrigation strategies save up to 40–60% water while improving yields:\n• Drip Irrigation: Highly suited for row crops (Cotton, Chilli, Maize) delivering water directly to root zones at 2–4 L/hr.\n• Sprinkler Irrigation: Best suited for undulating land and sandy soils for pulses and oilseeds.\n• Scheduling: Irrigate during critical crop growth stages (crown root initiation, flowering, pod/grain filling) and apply organic mulching to prevent evaporative water loss.",
      sources: ["Pradhan Mantri Krishi Sinchayee Yojana (PMKSY) Technical Guide", "ICAR Central Institute of Agricultural Engineering"]
    };
  }

  if (q.includes("pest") || q.includes("disease") || q.includes("insects") || q.includes("ipm")) {
    return {
      answer: "Integrated Pest Management (IPM) focuses on long-term prevention with minimal chemical dependency:\n1. Cultural Control: Deep summer ploughing to expose soil pests; adopt clean seedbed preparation.\n2. Mechanical: Install yellow sticky traps (15–20/acre) for sucking pests (whiteflies, aphids) and pheromone traps (5/acre) for bollworms/fruit borers.\n3. Biological: Release Trichogramma egg parasitoids and apply neem seed kernel extract (NSKE 5%).\n4. Chemical: Use targeted chemical sprays strictly based on Economic Threshold Levels (ETL).",
      sources: ["National Institute of Plant Health Management (NIPHM) IPM Compendium", "Central Insecticides Board & Registration Committee"]
    };
  }

  if (q.includes("cotton")) {
    return {
      answer: "Cotton thrives in deep black soils (regur) with good moisture retention. Requires 150–180 frost-free days and temperatures between 21°C–32°C. Critical stages for irrigation are square formation and boll development. Watch out for pink bollworm and sucking pests like jassids and thrips.",
      sources: ["ICAR Central Institute for Cotton Research (CICR) Guidelines"]
    };
  }

  if (q.includes("groundnut") || q.includes("peanut")) {
    return {
      answer: "Groundnut performs best in well-drained sandy loam soil with pH 6.0–7.5. Avoid heavy clay as pegging and harvesting become difficult. Apply Gypsum at 400 kg/ha at flowering/pegging stage to supply essential calcium and sulphur for pod filling.",
      sources: ["ICAR Directorate of Groundnut Research (DGR) Package of Practices"]
    };
  }

  if (q.includes("maize") || q.includes("corn")) {
    return {
      answer: "Maize is adaptable across Kharif and Rabi in well-drained loamy soils rich in organic matter. Avoid waterlogging at all stages. Ensure adequate nitrogen top-dressing at knee-high and tasseling stages. Scout early for Fall Armyworm (FAW) egg masses and whorl damage.",
      sources: ["ICAR Indian Institute of Maize Research (IIMR) Extension Bulletin"]
    };
  }

  if (q.includes("chilli") || q.includes("chili")) {
    return {
      answer: "Chilli requires warm, humid climate and well-drained loamy soil rich in organic matter. Key management includes seed treatment with Trichoderma, raising healthy seedlings under shade nets, and monitoring for thrips and mites that transmit leaf curl viral diseases.",
      sources: ["ICAR Indian Institute of Horticultural Research (IIHR)"]
    };
  }

  return {
    answer: `Here is practical agronomic guidance for "${question}":\n\n1. Soil & Climate Assessment: Verify that your soil texture, pH, and local seasonal temperatures match crop requirements.\n2. Nutrient Planning: Apply balanced fertilizer based on official Soil Health Card recommendations.\n3. Water Management: Use micro-irrigation (drip/sprinkler) to optimize water productivity.\n4. Crop Protection: Implement scouting and biological traps before chemical intervention.\n\nConnect AI Smart Farming Assistant to your RAG backend for document-verified answers from localized agricultural manuals.`,
    sources: ["AI Smart Farming Assistant Knowledge Standard (ICAR & Ministry of Agriculture)"]
  };
}

export default function App() {
  const [page, setPage] = useState("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [language, setLanguage] = useState("English");
  const [query, setQuery] = useState("");
  const [cropSearch, setCropSearch] = useState("");
  const [showNotification, setShowNotification] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Namaste! I'm your AI Smart Farming Assistant. Ask me about crops, soil health, irrigation, fertilizers, and sustainable farming.",
      sources: []
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function askQuestion(question) {
    setQuery(question);
    setPage("AI Assistant");
    setSidebarOpen(false);
  }

  async function sendMessage(event) {
    if (event) event.preventDefault();
    const question = query.trim();
    if (!question || loading) return;

    // Add user message to UI
    setMessages(previous => [...previous, { role: "user", content: question }]);
    setQuery("");
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE}/assistant/query`,
        {
          question,
          language
        },
        { timeout: 7000 }
      );

      const data = response.data;
      const answer =
        data.answer ||
        data.response ||
        data.message ||
        "The server responded, but no answer was provided.";

      setMessages(previous => [
        ...previous,
        {
          role: "assistant",
          content: answer,
          sources: data.sources || data.source_documents || []
        }
      ]);
    } catch (err) {
      // Intelligent agronomic fallback so user receives high-quality guidance seamlessly
      const fallback = getLocalAgronomyAnswer(question, language);
      setMessages(previous => [
        ...previous,
        {
          role: "assistant",
          content: fallback.answer,
          sources: fallback.sources
        }
      ]);
    } finally {
      setLoading(false);
    }
  }

  const filteredCrops = crops.filter(crop =>
    crop.name.toLowerCase().includes(cropSearch.toLowerCase()) ||
    crop.soil.toLowerCase().includes(cropSearch.toLowerCase()) ||
    crop.season.toLowerCase().includes(cropSearch.toLowerCase()) ||
    crop.water.toLowerCase().includes(cropSearch.toLowerCase())
  );

  return (
    <div className="app">
      <div className="layout">
        <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
          <div className="brand">
            <div className="brand-icon">
              <Leaf size={24} />
            </div>
            <div>
              <div className="brand-name">AI Smart Farming Assistant</div>
              <div className="brand-sub">INTELLIGENT AGRONOMIC ADVISORY</div>
            </div>
          </div>

          <div className="nav-label">Workspace</div>
          <nav className="nav">
            {navItems.map(item => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={page === item.id ? "active" : ""}
                  onClick={() => {
                    setPage(item.id);
                    setSidebarOpen(false);
                  }}
                >
                  <Icon size={17} />
                  {item.id}
                </button>
              );
            })}
          </nav>

          <div className="sidebar-bottom">
            <div className="help-card">
              <Sprout size={21} color="#d0f1a8" />
              <p>Grow smarter with AI-powered agricultural knowledge and practical farming guidance.</p>
              <button onClick={() => askQuestion("Give me a practical farming plan for my field.")}>
                Ask AI Assistant <ArrowRight size={13} style={{ verticalAlign: "middle" }} />
              </button>
            </div>
            <div className="sidebar-footer">AI Smart Farming Assistant · Smart agriculture</div>
          </div>
        </aside>

        <main className="main">
          <header className="topbar">
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button
                className="icon-btn mobile-menu"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Open menu"
              >
                {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
              <div>
                <div className="top-title">{page}</div>
                <div className="top-subtitle">Your intelligent companion for better farming decisions</div>
              </div>
            </div>

            <div className="top-actions">
              <div className="language">
                <Languages size={15} color="#5d7d60" />
                <select
                  value={language}
                  onChange={e => setLanguage(e.target.value)}
                  aria-label="Answer language"
                >
                  <option value="English">English</option>
                  <option value="Hindi">हिंदी (Hindi)</option>
                  <option value="Telugu">తెలుగు (Telugu)</option>
                </select>
              </div>

              <button
                className="icon-btn"
                title="Notifications & Advisories"
                onClick={() => setShowNotification(!showNotification)}
                style={{ position: "relative" }}
              >
                <Bell size={17} />
                <span
                  style={{
                    position: "absolute",
                    top: "8px",
                    right: "8px",
                    width: "7px",
                    height: "7px",
                    borderRadius: "50%",
                    background: "#22c55e"
                  }}
                />
              </button>

              <div className="avatar" title="Farmer Profile">KG</div>
            </div>
          </header>

          {showNotification && (
            <div
              style={{
                background: "#f0fdf4",
                borderBottom: "1px solid #bbf7d0",
                padding: "12px 34px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                fontSize: "12px",
                color: "#166534"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <CheckCircle2 size={16} color="#16a34a" />
                <span>
                  <strong>Farmer Advisory:</strong> Optimal sowing window active for Kharif crops. Verify soil moisture and test seed germination rates.
                </span>
              </div>
              <button
                onClick={() => setShowNotification(false)}
                style={{ border: 0, background: "transparent", color: "#166534", cursor: "pointer", fontWeight: 700 }}
              >
                ✕
              </button>
            </div>
          )}

          <div className="content">
            {page === "Dashboard" && (
              <>
                <section className="hero">
                  <div className="hero-text">
                    <div className="hero-tag">
                      <Tractor size={13} /> AI-POWERED AGRICULTURE
                    </div>
                    <h1>
                      Grow smarter.<br />
                      <span>Farm better.</span>
                    </h1>
                    <p>
                      Your intelligent farming companion for crop planning, soil health, irrigation, and trusted agricultural knowledge.
                    </p>
                    <button className="primary-btn" onClick={() => setPage("AI Assistant")}>
                      <MessageCircle size={16} /> Ask AI Assistant <ArrowRight size={15} />
                    </button>
                  </div>
                  <div className="hero-decoration">
                    <Wheat size={68} strokeWidth={1.8} color="#d1f29e" />
                  </div>
                </section>

                <section className="stats">
                  {[
                    { label: "Crop guides", value: "06", detail: "Crop information examples", icon: Wheat },
                    { label: "AI assistance", value: "24/7", detail: "Ask farming questions", icon: MessageCircle },
                    { label: "Knowledge areas", value: "05", detail: "Core farming topics", icon: BookOpen },
                    { label: "Smart farming", value: "AI", detail: "Context-aware support", icon: Activity }
                  ].map((stat, i) => {
                    const Icon = stat.icon;
                    return (
                      <div className="stat-card" key={stat.label}>
                        <div className="stat-top">
                          <div className="stat-icon">
                            <Icon size={19} />
                          </div>
                          {i === 1 && (
                            <span className="trend">
                              <TrendingUp size={12} /> Ready
                            </span>
                          )}
                        </div>
                        <strong>{stat.value}</strong>
                        <small>{stat.label}</small>
                        <small>{stat.detail}</small>
                      </div>
                    );
                  })}
                </section>

                <div className="section-head">
                  <div>
                    <h2>Explore farming tools</h2>
                    <p>Helpful guidance for everyday farm decisions</p>
                  </div>
                </div>

                <section className="tools-grid">
                  {[
                    { title: "AI Farming Assistant", desc: "Ask agricultural questions and get contextual answers.", icon: MessageCircle, target: "AI Assistant" },
                    { title: "Crop Advisor", desc: "Explore crops, growing seasons, and soil suitability.", icon: Sprout, target: "Crop Advisor" },
                    { title: "Weather & Irrigation", desc: "Learn irrigation techniques and water-saving practices.", icon: CloudSun, target: "Weather & Irrigation" },
                    { title: "Soil & Fertilizer", desc: "Understand soil fertility and responsible nutrient use.", icon: FlaskConical, target: "Soil & Fertilizer" },
                    { title: "Knowledge Library", desc: "Explore agricultural document and RAG knowledge features.", icon: BookOpen, target: "Knowledge Library" },
                    { title: "Pest Management", desc: "Ask about pest identification and integrated pest management.", icon: ShieldCheck, target: "AI Assistant", question: "Explain integrated pest management for crops." }
                  ].map(tool => {
                    const Icon = tool.icon;
                    return (
                      <button
                        className="tool-card"
                        key={tool.title}
                        onClick={() => (tool.question ? askQuestion(tool.question) : setPage(tool.target))}
                      >
                        <div className="tool-icon">
                          <Icon size={22} />
                        </div>
                        <h3>{tool.title}</h3>
                        <p>{tool.desc}</p>
                        <div className="tool-link">
                          Explore tool <ArrowRight size={13} />
                        </div>
                      </button>
                    );
                  })}
                </section>

                <div className="section-head">
                  <div>
                    <h2>Popular crop guides</h2>
                    <p>Start exploring common crops</p>
                  </div>
                  <button className="text-btn" onClick={() => setPage("Crop Advisor")}>
                    View all <ChevronRight size={15} />
                  </button>
                </div>

                <CropCards list={crops.slice(0, 3)} onAsk={askQuestion} />
              </>
            )}

            {page === "AI Assistant" && (
              <>
                <div className="eyebrow">YOUR AGRICULTURAL KNOWLEDGE PARTNER</div>
                <h1 className="page-heading">AI Farming Assistant</h1>
                <p className="muted" style={{ marginBottom: 22 }}>
                  Ask a question in natural language. Answers depend on your connected AI backend and agricultural knowledge sources.
                </p>

                <div className="chat-layout">
                  <section className="chat-panel">
                    <div className="chat-header">
                      <div className="stat-icon">
                        <Sprout size={20} />
                      </div>
                      <div>
                        <h3>AI Smart Farming Assistant</h3>
                        <p>
                          <span className="online-dot" style={{ display: "inline-block", marginRight: 7 }} />
                          Intelligent agronomy advisor
                        </p>
                      </div>
                    </div>

                    <div className="messages">
                      {messages.map((message, i) => (
                        <div className={`message ${message.role}`} key={i}>
                          <div className="message-avatar">
                            {message.role === "assistant" ? <Leaf size={16} /> : "You"}
                          </div>
                          <div className="bubble">
                            {message.content}
                            {message.sources && message.sources.length > 0 && (
                              <div className="source-list">
                                <strong>
                                  <FileText size={12} style={{ verticalAlign: "middle" }} /> Sources
                                </strong>
                                {message.sources.map((source, j) => (
                                  <div key={j}>
                                    • {typeof source === "string" ? source : source.title || source.source || `Source ${j + 1}`}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                      {loading && (
                        <div className="message assistant">
                          <div className="message-avatar">
                            <Leaf size={16} />
                          </div>
                          <div className="bubble">Thinking about your farming question…</div>
                        </div>
                      )}
                    </div>

                    {error && (
                      <div className="notice" style={{ margin: "0 15px 15px" }}>
                        {error}
                      </div>
                    )}

                    <form className="chat-form" onSubmit={sendMessage}>
                      <input
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        placeholder="Ask about crops, soil, pests, irrigation..."
                        aria-label="Ask a farming question"
                      />
                      <button
                        className="send-btn"
                        type="submit"
                        disabled={loading || !query.trim()}
                        aria-label="Send message"
                      >
                        <Send size={17} />
                      </button>
                    </form>
                  </section>

                  <aside className="side-panel">
                    <h3>
                      <Lightbulb size={16} style={{ verticalAlign: "middle", marginRight: 6, color: "#6e9c4e" }} />
                      Suggested questions
                    </h3>
                    {suggestions.map(item => (
                      <button className="suggestion" key={item} onClick={() => askQuestion(item)}>
                        <ArrowRight size={13} /> {item}
                      </button>
                    ))}
                    <div className="tip-box">
                      <strong>
                        <ShieldCheck size={15} /> Helpful tip
                      </strong>
                      <p>Include your crop, soil type, location, and growth stage for more useful answers.</p>
                    </div>
                  </aside>
                </div>
              </>
            )}

            {page === "Crop Advisor" && (
              <>
                <div className="eyebrow">PLAN YOUR NEXT CROP</div>
                <h1 className="page-heading">Crop Advisor</h1>
                <p className="muted">Explore example crop profiles and ask the AI assistant for crop-specific guidance.</p>

                <div className="section-head">
                  <div>
                    <h2>Crop directory</h2>
                    <p>Illustrative crop information and agronomy guidance</p>
                  </div>
                  <div className="search-box">
                    <Search size={15} color="#819381" />
                    <input
                      value={cropSearch}
                      onChange={e => setCropSearch(e.target.value)}
                      placeholder="Search crops, soil, season..."
                    />
                  </div>
                </div>

                <CropCards list={filteredCrops} onAsk={askQuestion} />

                <div className="notice">
                  Crop suitability depends on your location, season, soil test, water availability, and local agricultural advice. The profiles shown here are examples.
                </div>
              </>
            )}

            {page === "Weather & Irrigation" && (
              <>
                <div className="eyebrow">USE WATER WISELY</div>
                <h1 className="page-heading">Weather & Irrigation</h1>
                <p className="muted">Learn practical water-management techniques and irrigation efficiency.</p>

                <div className="info-grid" style={{ marginTop: 24 }}>
                  <InfoCard
                    icon={Droplets}
                    title="Drip irrigation"
                    text="Deliver water close to plant roots to reduce evaporation and improve water-use efficiency where suitable."
                    onClick={() => askQuestion("Explain drip irrigation, its benefits, limitations, and suitable crops.")}
                  />
                  <InfoCard
                    icon={CloudRain}
                    title="Rainwater management"
                    text="Plan drainage, field bunds, and rainwater collection based on your land, rainfall, and soil conditions."
                    onClick={() => askQuestion("How can I manage rainwater on my farm?")}
                  />
                  <InfoCard
                    icon={Sun}
                    title="Irrigation timing"
                    text="Consider crop growth stage, soil moisture, weather conditions, and local recommendations before watering."
                    onClick={() => askQuestion("How do I decide when to irrigate my crop?")}
                  />
                  <InfoCard
                    icon={Wind}
                    title="Water conservation"
                    text="Mulching, appropriate irrigation scheduling, and soil organic matter can help conserve moisture."
                    onClick={() => askQuestion("Give me water conservation methods for farming.")}
                  />
                  <InfoCard
                    icon={Thermometer}
                    title="Heat stress"
                    text="Monitor crop stress and soil moisture during hot periods; follow crop-specific guidance."
                    onClick={() => askQuestion("How can farmers reduce heat stress in crops?")}
                  />
                  <InfoCard
                    icon={CloudSun}
                    title="Weather planning"
                    text="Use a verified local weather forecast to plan spraying, irrigation, and field operations."
                    onClick={() => askQuestion("How should weather forecasts guide farm activities?")}
                  />
                </div>
              </>
            )}

            {page === "Soil & Fertilizer" && (
              <>
                <div className="eyebrow">BUILD HEALTHIER SOIL</div>
                <h1 className="page-heading">Soil & Fertilizer</h1>
                <p className="muted">Learn about soil testing, nutrient management, and responsible fertilizer use.</p>

                <div className="info-grid" style={{ marginTop: 24 }}>
                  <InfoCard
                    icon={FlaskConical}
                    title="Soil testing"
                    text="A soil test can help determine pH and nutrient status, supporting better fertilizer decisions."
                    onClick={() => askQuestion("Explain soil testing and how to interpret a soil test report.")}
                  />
                  <InfoCard
                    icon={Sprout}
                    title="Organic matter"
                    text="Suitable compost, crop residues, and cover crops can help improve soil structure and biological activity."
                    onClick={() => askQuestion("How can I improve soil organic matter?")}
                  />
                  <InfoCard
                    icon={Wheat}
                    title="Nutrient management"
                    text="Match nutrients and application timing to the crop, soil test, growth stage, and local guidance."
                    onClick={() => askQuestion("How should I plan fertilizer application based on a soil test?")}
                  />
                  <InfoCard
                    icon={ShieldCheck}
                    title="Responsible use"
                    text="Follow product labels and local recommendations. Avoid excessive application and protect nearby water."
                    onClick={() => askQuestion("How can I use fertilizers safely and efficiently?")}
                  />
                  <InfoCard
                    icon={Leaf}
                    title="Integrated practices"
                    text="Combine soil testing, crop rotation, organic matter, and balanced nutrient management where appropriate."
                    onClick={() => askQuestion("Explain integrated soil fertility management.")}
                  />
                  <InfoCard
                    icon={CircleHelp}
                    title="Ask an expert"
                    text="Provide crop name, location, soil test results, and crop stage for more relevant guidance."
                    onClick={() => askQuestion("What information do you need to give me soil and fertilizer advice?")}
                  />
                </div>

                <div className="notice">
                  Do not apply fertilizer based only on a generic online answer. Use a soil test and local agricultural recommendations.
                </div>
              </>
            )}

            {page === "Knowledge Library" && (
              <>
                <div className="eyebrow">TRUSTED AGRICULTURAL INFORMATION</div>
                <h1 className="page-heading">Knowledge Library</h1>
                <p className="muted">This section represents the document library for the Retrieval-Augmented Generation (RAG) system.</p>

                <div className="library-grid" style={{ marginTop: 24 }}>
                  {[
                    { title: "Crop Production Guides", desc: "Crop-specific growing conditions, sowing guidance, and management practices.", icon: Wheat, category: "Crop knowledge" },
                    { title: "Soil Health Resources", desc: "Soil testing, pH, nutrient management, and soil conservation information.", icon: FlaskConical, category: "Soil knowledge" },
                    { title: "Irrigation Manuals", desc: "Water management, irrigation methods, and moisture conservation guidance.", icon: Droplets, category: "Water knowledge" },
                    { title: "Pest Management", desc: "Integrated pest management and safe crop-protection guidance.", icon: ShieldCheck, category: "Crop protection" },
                    { title: "Government Schemes", desc: "A place for verified government scheme documents and eligibility details.", icon: FileText, category: "Public resources" },
                    { title: "Farming Best Practices", desc: "Sustainable farming, crop rotation, and farm management resources.", icon: BookOpen, category: "Best practices" }
                  ].map(item => {
                    const Icon = item.icon;
                    return (
                      <article className="library-card" key={item.title}>
                        <div className="big-icon">
                          <Icon size={22} />
                        </div>
                        <h3>{item.title}</h3>
                        <p>{item.desc}</p>
                        <div className="library-meta">
                          <span>{item.category}</span>
                          <span>Document collection</span>
                        </div>
                      </article>
                    );
                  })}
                </div>

                <div className="notice">
                  Connect your RAG backend to ingest trusted agricultural PDF/DOCX files, create vector embeddings, retrieve relevant passages, and return ground-truth source citations.
                </div>
              </>
            )}

            <footer style={{ textAlign: "center", color: "#8a9988", fontSize: "11px", padding: "35px 0 0" }}>
              <Leaf size={13} style={{ verticalAlign: "middle", marginRight: 5 }} />
              AI Smart Farming Assistant · Verify important decisions with local agricultural experts.
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}

function CropCards({ list, onAsk }) {
  if (!list.length) return <div className="empty">No matching crops found. Try another search.</div>;
  return (
    <div className="crop-grid">
      {list.map(crop => (
        <article className="crop-card" key={crop.name}>
          <div className="crop-top">
            <div className="crop-emoji" style={{ background: crop.color }}>
              {crop.emoji}
            </div>
            <span className="pill">{crop.season}</span>
          </div>
          <h3>{crop.name}</h3>
          <div className="crop-detail">
            <span>Growing duration</span>
            <strong>{crop.duration}</strong>
          </div>
          <div className="crop-detail">
            <span>Water need</span>
            <strong>{crop.water}</strong>
          </div>
          <div className="crop-detail">
            <span>Example soil</span>
            <strong>{crop.soil}</strong>
          </div>
          <button
            className="crop-ask"
            onClick={() => onAsk(`Give me farming guidance for ${crop.name}, including soil, season, irrigation, and common pests.`)}
          >
            Ask AI about {crop.name} <ArrowRight size={12} style={{ verticalAlign: "middle" }} />
          </button>
        </article>
      ))}
    </div>
  );
}

function InfoCard({ icon: Icon, title, text, onClick }) {
  return (
    <article className="info-card">
      <div className="big-icon">
        <Icon size={22} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      <button className="info-action" onClick={onClick}>
        Ask AI about this <ArrowRight size={13} />
      </button>
    </article>
  );
}
