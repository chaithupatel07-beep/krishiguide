from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.core.logging import logger

VERIFIED_SEED_DOCUMENTS = [
    {
        "document_name": "Rice_Cultivation_Manual.pdf",
        "file_type": "application/pdf",
        "file_size": 2400000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 12,
                "text": (
                    "For paddy (rice) crop, urea, DAP and MOP are commonly recommended fertilizers. "
                    "The typical dosage is 40-60 kg N, 20-25 kg P2O5, and 20-25 kg K2O per hectare. "
                    "You can also use organic manure for better soil health. Apply 50% nitrogen as basal dose, "
                    "25% at active tillering, and 25% at panicle initiation stage. Source: ICAR - Paddy Cultivation Manual."
                ),
            },
            {
                "page_number": 15,
                "text": (
                    "Paddy Yellow Stem Borer (Scirpophaga incertulas) management: "
                    "Symptoms include dead hearts in vegetative phase and white ears at panicle stage. "
                    "IPM Protocol: Install pheromone traps at 5 per acre. Avoid excess nitrogen. "
                    "Chemical control: Spray Chlorantraniliprole 18.5% SC @ 60 ml/acre or Cartap Hydrochloride 50% SP @ 400 g/acre."
                ),
            },
            {
                "page_number": 19,
                "text": (
                    "Rice Leaf Folder (Cnaphalocrocis medinalis) control: "
                    "Larvae fold leaves longitudinally and scrape the green tissue, causing white transparent streaks. "
                    "Release egg parasitoid Trichogramma chilonis @ 1,00,000/ha. If damage exceeds 10% flag leaf injury, "
                    "apply Flubendiamide 39.35% SC @ 20-25 ml/acre."
                ),
            },
        ],
    },
    {
        "document_name": "Soil_Health_Guide.pdf",
        "file_type": "application/pdf",
        "file_size": 1800000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 3,
                "text": (
                    "Soil pH value for maize should ideally be between 6.0 and 7.5 for maximum nutrient availability. "
                    "Maize is moderately sensitive to soil acidity. If pH is below 5.5, apply agricultural lime (calcium carbonate) "
                    "at 2 to 3 tonnes per hectare before land preparation. Ensure deep ploughing and FYM application."
                ),
            },
            {
                "page_number": 8,
                "text": (
                    "Soil Organic Carbon (SOC) management: Indian agricultural soils generally contain less than 0.5% SOC. "
                    "Incorporate green manure crops like Sunnhemp or Dhaincha at flowering stage. Apply Farm Yard Manure (FYM) "
                    "or vermicompost at 5-10 tonnes/ha to improve microbial activity and water holding capacity."
                ),
            },
        ],
    },
    {
        "document_name": "Pest_Management.pdf",
        "file_type": "application/pdf",
        "file_size": 3200000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 5,
                "text": (
                    "Integrated Pest Management (IPM) core principles: "
                    "1. Cultural controls (crop rotation, clean cultivation). "
                    "2. Mechanical controls (light traps, pheromone traps, yellow/blue sticky cards @ 10-15 per acre). "
                    "3. Biological controls (Chrysoperla, Trichogramma, neem formulations). "
                    "4. Judicious chemical application strictly based on Economic Threshold Level (ETL)."
                ),
            },
            {
                "page_number": 14,
                "text": (
                    "Tomato Early Blight and Late Blight identification & management: "
                    "Concentric dark brown rings appear on lower foliage ('target board' effect). "
                    "Preventive spray: Mancozeb 75% WP @ 2.5 g/L or Copper Oxychloride 50% WP @ 3 g/L. "
                    "Curative spray: Metalaxyl 8% + Mancozeb 64% WP @ 2 g/L or Azoxystrobin 23% SC @ 1 ml/L."
                ),
            },
        ],
    },
    {
        "document_name": "Government_Schemes.pdf",
        "file_type": "application/pdf",
        "file_size": 2100000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 2,
                "text": (
                    "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi): "
                    "Provides financial assistance of ₹6,000 per annum to eligible landholder farmer families, "
                    "payable in three equal instalments of ₹2,000 every 4 months directly into Aadhaar-seeded bank accounts. "
                    "Official portal: pmkisan.gov.in."
                ),
            },
            {
                "page_number": 4,
                "text": (
                    "PMFBY (Pradhan Mantri Fasal Bima Yojana): "
                    "Comprehensive risk insurance for crop loss due to non-preventable natural risks. "
                    "Farmer premium share: 2% for Kharif food and oilseed crops, 1.5% for Rabi food and oilseed crops, "
                    "and 5% for annual commercial/horticultural crops. Government subsidizes the rest. Official portal: pmfby.gov.in."
                ),
            },
        ],
    },
    {
        "document_name": "Irrigation_Scheduling.pdf",
        "file_type": "application/pdf",
        "file_size": 1500000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 7,
                "text": (
                    "Alternate Wetting and Drying (AWD) for Paddy: "
                    "A perforated plastic pipe (field water tube) of 30 cm length and 15 cm diameter is installed in the field. "
                    "Irrigation is applied only when the water level inside the tube drops to 15 cm below the soil surface. "
                    "This saves 15-30% irrigation water with zero yield penalty and suppresses methane emissions."
                ),
            },
            {
                "page_number": 11,
                "text": (
                    "Drip Irrigation Setup and Water Scheduling for Tomato & Chilli: "
                    "Operating pressure: 1.0 to 1.2 kg/cm2. In-line emitter spacing: 30-40 cm with 2 to 4 LPH drippers. "
                    "Daily water requirement: 3-5 litres per plant in vegetative stage, increasing to 6-8 litres during fruiting. "
                    "Reduces weed proliferation and fertilizer leaching by up to 45% through fertigation."
                ),
            },
        ],
    },
    {
        "document_name": "Cotton_Production_Technology.pdf",
        "file_type": "application/pdf",
        "file_size": 2850000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 8,
                "text": (
                    "Bt Cotton Spacing and High-Density Planting System (HDPS): "
                    "For deep black soils, optimal spacing is 90 x 45 cm (24,691 plants/ha). "
                    "Apply recommended NPK 120:60:60 kg/ha. Apply 25% Nitrogen at sowing, 50% at square formation (45 DAS), "
                    "and 25% at flowering. Spray 2% Potassium Nitrate (13:0:45) at boll development to prevent leaf reddening."
                ),
            },
            {
                "page_number": 21,
                "text": (
                    "Pink Bollworm (Pectinophora gossypiella) IPM in Cotton: "
                    "Install gossyplure pheromone traps @ 5/acre for monitoring and 15-20/acre for mass trapping. "
                    "Release egg parasitoid Trichogramma bactrae @ 60,000/acre at weekly intervals. "
                    "If rosette flowers exceed 5-10% or green boll damage exceeds 10%, spray Profenofos 50% EC @ 2 ml/L or Chlorpyriphos 20% EC @ 2.5 ml/L."
                ),
            },
        ],
    },
    {
        "document_name": "Maize_Crop_Production_Guide.pdf",
        "file_type": "application/pdf",
        "file_size": 2150000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 12,
                "text": (
                    "Maize High-Yield Agronomy & Fertilizer Schedule: "
                    "Optimum seed rate is 20 kg/ha for hybrids with spacing of 60 x 20 cm. "
                    "Apply 120-150 kg N, 60 kg P2O5, and 40 kg K2O per hectare. Apply full P, full K, and 1/3rd N as basal dose. "
                    "Top dress remaining Nitrogen in two equal splits: 1/3rd at knee-high stage (V6, 30-35 DAS) and 1/3rd at tasseling."
                ),
            },
            {
                "page_number": 18,
                "text": (
                    "Fall Armyworm (Spodoptera frugiperda) Management in Maize: "
                    "Scout for pinhole whorl damage. Apply push-pull strategy with Desmodium and Napier grass border. "
                    "Early stage bio-control: Spray Bacillus thuringiensis (Bt) @ 2 g/L or Metarhizium rileyi @ 3 g/L. "
                    "Severe infestation (ETL > 10% damaged whorls): Direct spray into whorls with Chlorantraniliprole 18.5% SC @ 0.4 ml/L or Emamectin Benzoate 5% SG @ 0.4 g/L."
                ),
            },
        ],
    },
    {
        "document_name": "Chilli_Crop_Management.pdf",
        "file_type": "application/pdf",
        "file_size": 2600000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 14,
                "text": (
                    "Chilli Sucking Pest Complex (Thrips vs Mites Differentiation): "
                    "Thrips (Scirtothrips dorsalis) cause leaves to curl upwards with silvery boat-shaped underside. "
                    "Yellow mites (Polyphagotarsonemus latus) cause downward curling ('inverted cup') with elongated petiole. "
                    "For thrips: Spray Fipronil 5% SC @ 2 ml/L or Spinosad 45% SC @ 0.3 ml/L. "
                    "For mites: Spray Spiromesifen 22.9% SC @ 1 ml/L or Diafenthiuron 50% WP @ 1.25 g/L."
                ),
            },
            {
                "page_number": 26,
                "text": (
                    "Anthracnose / Die-back and Fruit Rot (Colletotrichum capsici) in Chilli: "
                    "Symptoms include necrosis of tender twigs starting from top downwards and circular sunken spots on ripe fruits. "
                    "Spray Azoxystrobin 23% SC @ 1 ml/L or Difenoconazole 25% EC @ 0.5 ml/L or Copper Oxychloride @ 3 g/L at 12-day intervals."
                ),
            },
        ],
    },
    {
        "document_name": "Groundnut_Package_of_Practices.pdf",
        "file_type": "application/pdf",
        "file_size": 1900000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 9,
                "text": (
                    "Groundnut Calcium Nutrition & Gypsum Application: "
                    "Groundnut pods absorb calcium directly from the pegging zone soil, not through root xylem. "
                    "Apply Gypsum @ 400-500 kg/ha at peak flowering (40-45 DAS) close to the base of plants and lightly incorporate into soil. "
                    "This prevents 'pops' (empty shells) and increases oil content and kernel weight."
                ),
            },
            {
                "page_number": 16,
                "text": (
                    "Tikka Leaf Spot (Cercospora arachidicola) Control: "
                    "Dark brown to black circular spots surrounded by a chlorotic yellow halo appear on leaves. "
                    "Spray Tebuconazole 25.9% EC @ 1.25 ml/L or Hexaconazole 5% EC @ 2 ml/L at first appearance of disease."
                ),
            },
        ],
    },
    {
        "document_name": "Redgram_Pigeonpea_Manual.pdf",
        "file_type": "application/pdf",
        "file_size": 2100000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 6,
                "text": (
                    "Pigeonpea (Arhar / Redgram) Agronomy & Seed Treatment: "
                    "Inoculate seeds with Rhizobium culture and Trichoderma viride @ 5 g/kg seed before sowing. "
                    "Spacing: 150-180 x 20 cm for medium-duration varieties like Asha (ICPL 87119). "
                    "Apply 20 kg N, 50 kg P2O5, and 20 kg Sulphur per hectare as basal placement."
                ),
            },
            {
                "page_number": 18,
                "text": (
                    "Helicoverpa Pod Borer Management in Pigeonpea: "
                    "Monitor moths with pheromone traps @ 5/acre. Shake plants over plastic sheets to dislodge early instars. "
                    "Spray HaNPV (250 LE/ha) or Neem oil 1500 ppm @ 3 ml/L at 50% flowering. "
                    "For late instars, spray Chlorantraniliprole 18.5% SC @ 0.3 ml/L or Flubendiamide 480 SC @ 0.2 ml/L."
                ),
            },
        ],
    },
    {
        "document_name": "Wheat_Cultivation_Practices.pdf",
        "file_type": "application/pdf",
        "file_size": 2400000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 10,
                "text": (
                    "Wheat Sowing Time & Critical Irrigation Stages: "
                    "Optimum sowing window: Nov 1 to Nov 20. Crown Root Initiation (CRI) stage (20-25 DAS) is the most critical irrigation stage; "
                    "delaying CRI irrigation by 10 days can cause irreversible yield reduction of up to 10 quintals/ha. "
                    "Subsequent critical stages: Tillering (40-45 DAS), Jointing (60-65 DAS), Flowering (80-85 DAS), and Milk stage (100-105 DAS)."
                ),
            },
            {
                "page_number": 22,
                "text": (
                    "Stripe Rust (Yellow Rust) Management in Wheat: "
                    "Yellow pustules arranged in linear stripes appear on leaves. "
                    "Spray Propiconazole 25% EC (Tilt) @ 1 ml/L (200 ml in 200L water/acre) immediately upon first sighting in cooler sub-mountainous zones."
                ),
            },
        ],
    },
    {
        "document_name": "Soybean_Production_Guide.pdf",
        "file_type": "application/pdf",
        "file_size": 2050000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 7,
                "text": (
                    "Soybean Broad Bed Furrow (BBF) System & Weed Management: "
                    "Plant on broad beds of 120 cm width with 30 cm furrows to facilitate drainage in heavy Vertisols during waterlogging. "
                    "Apply pre-emergence herbicide Pendimethalin 30% EC @ 1.0 kg a.i./ha within 48 hours of sowing, or post-emergence Imazethapyr 10% SL @ 100 g a.i./ha at 15-20 DAS."
                ),
            },
            {
                "page_number": 15,
                "text": (
                    "Girdle Beetle (Obereopsis brevis) in Soybean: "
                    "Adult females make two parallel ring cuts around the petiole or stem and lay eggs. "
                    "Apply Thiamethoxam 12.6% + Lambda Cyhalothrin 9.5% ZC @ 0.25 ml/L of water at early vegetative stage."
                ),
            },
        ],
    },
    {
        "document_name": "Sugarcane_Cultivation_Standard.pdf",
        "file_type": "application/pdf",
        "file_size": 3100000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 12,
                "text": (
                    "Sugarcane Sett Treatment & Planting: "
                    "Dip 2-bud setts in Carbendazim 50% WP (1 g/L) + Chlorpyriphos 20% EC (2 ml/L) solution for 15 minutes before furrow planting. "
                    "Recommended spacing is 120 cm or 150 cm single row or 30-150-30 cm dual row under drip fertigation. "
                    "Apply 250:100:120 kg NPK/ha; complete all Nitrogen by 90-120 days after planting (prior to grand growth phase)."
                ),
            },
            {
                "page_number": 28,
                "text": (
                    "Early Shoot Borer (Chilo infuscatellus) in Sugarcane: "
                    "Dead hearts appear in shoots up to 100 days old. "
                    "Apply Chlorantraniliprole 0.4% G @ 7.5 kg/acre in furrows at planting, or spray Chlorantraniliprole 18.5% SC @ 0.3 ml/L at 30 and 45 days after planting."
                ),
            },
        ],
    },
    {
        "document_name": "Horticulture_Mango_Orchard_Care.pdf",
        "file_type": "application/pdf",
        "file_size": 2750000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 15,
                "text": (
                    "Mango Hopper (Idioscopus clypealis) & Powdery Mildew Management: "
                    "Nymphs suck sap from tender panicles causing blossom blight and fruit drop. "
                    "First spray at flower bud emergence: Imidacloprid 17.8% SL @ 0.3 ml/L + Wettable Sulphur @ 2 g/L. "
                    "Second spray at fruit set (pea size): Hexaconazole 5% EC @ 1 ml/L + Thiamethoxam 25% WG @ 0.2 g/L."
                ),
            },
        ],
    },
    {
        "document_name": "Organic_Farming_Biofertilizers.pdf",
        "file_type": "application/pdf",
        "file_size": 1700000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 5,
                "text": (
                    "Jeevamrutha Preparation & Application Protocol: "
                    "Mix 10 kg fresh desi cow dung, 5-10 L cow urine, 2 kg jaggery, 2 kg pulse flour, and a handful of virgin forest/bund soil in 200 L water. "
                    "Ferment for 48-72 hours under shade, stirring clockwise twice daily. "
                    "Apply 200 L per acre via irrigation water or spray 10% filtered extract on crop canopy every 15-20 days to multiply beneficial soil microbiota."
                ),
            },
        ],
    },
    {
        "document_name": "Post_Harvest_Storage_Management.pdf",
        "file_type": "application/pdf",
        "file_size": 1950000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 8,
                "text": (
                    "Grain Safe Storage Moisture Limits & Hermetic Technology: "
                    "Sun-dry food grains to below 12% moisture (below 8% for oilseeds) prior to bag storage to prevent fungal aflatoxin contamination and insect infestation. "
                    "Use hermetic storage bags (PICS / SuperGrain bags) which naturally create high-CO2, oxygen-depleted atmospheres that suffocate stored grain weevils without chemical fumigants."
                ),
            },
        ],
    },
    {
        "document_name": "Weed_Management_Guide.pdf",
        "file_type": "application/pdf",
        "file_size": 2200000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 11,
                "text": (
                    "Integrated Weed Management & Herbicide Resistance Mitigation: "
                    "Rotate chemical modes of action (ALS inhibitors, ACCase inhibitors, and synthetic auxins) to prevent herbicide-resistant Phalaris minor and Echinochloa colona. "
                    "For transplanted rice: apply Pretilachlor 50% EC + safener @ 500 g a.i./ha within 3 days of transplanting into 2-3 cm standing water."
                ),
            },
        ],
    },
    {
        "document_name": "Precision_Farming_IoT_Sensors.pdf",
        "file_type": "application/pdf",
        "file_size": 1650000,
        "is_public": True,
        "chunks": [
            {
                "page_number": 4,
                "text": (
                    "IoT Soil Moisture Sensors & Smart Drip Automation: "
                    "Install capacitive FMC soil moisture probes at two root depths: 15 cm (active feeding zone) and 45 cm (deep reserve). "
                    "Trigger automated solenoid valve irrigation when tension reaches 30-40 kPa in sandy loam soils, conserving up to 35% electricity and water."
                ),
            },
        ],
    },
]


async def seed_verified_agricultural_documents(session: AsyncSession) -> int:
    """
    Seeds verified agricultural guidance documents and precomputed vector embeddings
    for any documents not yet in the database.
    """
    try:
        total_seeded = 0

        for doc_data in VERIFIED_SEED_DOCUMENTS:
            existing_doc = (await session.execute(
                select(Document).where(Document.document_name == doc_data["document_name"])
            )).scalars().first()

            if existing_doc:
                continue

            doc = Document(
                document_name=doc_data["document_name"],
                file_path=f"system_docs/{doc_data['document_name']}",
                file_type=doc_data["file_type"],
                file_size=doc_data["file_size"],
                is_public=True,
                processing_status="completed",
                meta_info={
                    "total_pages": len(doc_data["chunks"]),
                    "total_chunks": len(doc_data["chunks"]),
                    "source": "ICAR / Ministry of Agriculture verified",
                },
            )
            session.add(doc)
            await session.flush()  # assign doc.id

            vector_items = []
            for idx, c in enumerate(doc_data["chunks"]):
                vec = EmbeddingService.embed_text(c["text"])
                point_id = f"seed-doc{doc.id}-c{idx}"

                vector_items.append({
                    "point_id": point_id,
                    "vector": vec,
                    "payload": {
                        "document_id": doc.id,
                        "document_name": doc.document_name,
                        "page_number": c["page_number"],
                        "chunk_index": idx,
                        "chunk_text": c["text"],
                        "is_public": True,
                    },
                })

                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    chunk_text=c["text"],
                    page_number=c["page_number"],
                    vector_reference=point_id,
                    embedding=vec,
                    meta_info={"page": c["page_number"]},
                )
                session.add(chunk)

            # Store in vector store
            vector_store.upsert_chunks(vector_items)
            total_seeded += 1

        if total_seeded > 0:
            await session.commit()
            logger.info(f"Successfully seeded {total_seeded} verified agricultural documents into DB and vector store.")
        return total_seeded

    except Exception as e:
        logger.error(f"Error seeding verified documents: {e}", exc_info=True)
        await session.rollback()
        return 0



async def seed_expert_and_demo_cases(session: AsyncSession):
    """Seeds default verified agricultural expert, admin, farmer, demo consultation case, and notifications."""
    from app.models.user import User
    from app.models.farm_profile import FarmProfile
    from app.models.expert import AgriculturalExpert, ExpertCase, ExpertResponse, ExpertCaseHistory
    from app.models.notification import Notification
    from app.core.security import get_password_hash
    from datetime import datetime, timezone

    try:
        # 1. Admin Account
        admin = (await session.execute(select(User).where(User.email == "admin@smartfarming.org"))).scalars().first()
        if not admin:
            admin = User(
                full_name="AgriAI Administrator",
                email="admin@smartfarming.org",
                hashed_password=get_password_hash("admin123"),
                phone_number="+91 99000 11223",
                role="admin",
                account_status="active",
            )
            session.add(admin)
            await session.flush()
            logger.info("Seeded default admin user: admin@smartfarming.org")

        # 2. Agricultural Expert Account
        expert_user = (await session.execute(select(User).where(User.email == "expert@smartfarming.org"))).scalars().first()
        if not expert_user:
            expert_user = User(
                full_name="Dr. Sunita Rao",
                email="expert@smartfarming.org",
                hashed_password=get_password_hash("expert123"),
                phone_number="+91 98480 99887",
                role="expert",
                account_status="active",
            )
            session.add(expert_user)
            await session.flush()

            expert_profile = AgriculturalExpert(
                user_id=expert_user.id,
                qualification="Ph.D. Agronomy, ICAR-CRIDA Senior Scientist",
                specialization="Agronomy & Crop Protection",
                experience=14,
                state="Telangana",
                district="Hyderabad / Rangareddy",
                areas_of_expertise=["Rice", "Paddy", "Maize", "Cotton", "IPM", "Soil Health", "Drip Irrigation"],
                approval_status="approved",
                availability_status="available",
            )
            session.add(expert_profile)
            await session.flush()
            logger.info("Seeded default agricultural expert: Dr. Sunita Rao (expert@smartfarming.org)")

        # 3. Farmer Account
        farmer = (await session.execute(select(User).where(User.email == "ramesh.kumar@smartfarming.org"))).scalars().first()
        if not farmer:
            farmer = User(
                full_name="Ramesh Kumar",
                email="ramesh.kumar@smartfarming.org",
                hashed_password=get_password_hash("farmer123"),
                phone_number="+91 98480 12345",
                role="farmer",
                account_status="active",
            )
            session.add(farmer)
            await session.flush()

            farm_prof = FarmProfile(
                user_id=farmer.id,
                farm_location="Shamshabad, Rangareddy, Telangana",
                district="Rangareddy",
                village="Shamshabad",
                farm_size=5.50,
                soil_type="Clay Loam",
                crop_details=["Rice", "Paddy", "Maize"],
                irrigation_details={"method": "Canal & Borewell", "frequency": "Weekly"},
                preferred_language="English",
            )
            session.add(farm_prof)
            await session.flush()
            logger.info("Seeded default farmer user: Ramesh Kumar (ramesh.kumar@smartfarming.org)")

        # 4. Demo Consultation Case
        existing_case = (await session.execute(select(ExpertCase).where(ExpertCase.farmer_id == farmer.id))).scalars().first()
        if not existing_case:
            case = ExpertCase(
                farmer_id=farmer.id,
                expert_id=expert_user.id,
                crop_name="Paddy (Rice)",
                category="Pest & Disease Control",
                question="My paddy crop leaves are folded longitudinally and show transparent white patches with small green caterpillars inside. What is the emergency treatment?",
                farmer_question="My paddy crop leaves are folded longitudinally and show transparent white patches with small green caterpillars inside. What is the emergency treatment?",
                priority="high",
                status="answered",
                title="Paddy Leaf Folder Infestation - Emergency Treatment",
                ai_response_snapshot="Based on ICAR guidelines, this matches Rice Leaf Folder (Cnaphalocrocis medinalis). Recommended controls include releasing Trichogramma parasitoids and spraying Flubendiamide 39.35% SC.",
                source_references=["Rice_Cultivation_Manual.pdf (Page 19)", "Pest_Management.pdf (Page 5)"],
                expert_response="Confirmed Rice Leaf Folder (Cnaphalocrocis medinalis) exceeding Economic Threshold Level (10% flag leaf injury). Follow the exact dosage and precautions below.",
                recommendations=["Spray Chlorantraniliprole 18.5% SC @ 60 ml/acre or Flubendiamide 39.35% SC @ 25 ml/acre in 200L water", "Avoid top-dressing urea till pest is suppressed", "Release Trichogramma chilonis egg parasitoid @ 1,00,000/ha"],
            )
            session.add(case)
            await session.flush()

            # Structured Expert Response
            resp = ExpertResponse(
                case_id=case.id,
                expert_id=expert_user.id,
                response="Confirmed Rice Leaf Folder (Cnaphalocrocis medinalis) exceeding Economic Threshold Level (10% flag leaf injury). Follow the exact dosage and precautions below.",
                diagnosis="Rice Leaf Folder (Cnaphalocrocis medinalis) at maximum tillering stage. Excessive nitrogen top-dressing may have exacerbated succulent leaf tissue.",
                recommended_actions=[
                    "Spray Chlorantraniliprole 18.5% SC @ 60 ml/acre or Flubendiamide 39.35% SC @ 25 ml/acre in 200L water.",
                    "Release egg parasitoid Trichogramma chilonis @ 1,00,000/ha at 7-day intervals.",
                    "Immediately hold excess urea/nitrogen top-dressing for 10-12 days.",
                ],
                precautions=[
                    "Spray strictly between 3:30 PM and 6:00 PM when moths and larvae are active.",
                    "Wear protective mask and chemical-resistant gloves during preparation.",
                    "Do not allow livestock or poultry into the sprayed field for 7 days.",
                ],
                additional_suggestions="Maintain 5 cm standing water during the spray period to allow systemic absorption through the root zone.",
                supporting_references=[
                    "ICAR Package of Practices for Rice (2024 Edition, Page 19)",
                    "Directorate of Rice Research (IIRR) Technical Bulletin #42",
                ],
            )
            session.add(resp)

            # History
            hist = ExpertCaseHistory(
                case_id=case.id,
                previous_status="pending",
                new_status="answered",
                changed_by=expert_user.id,
            )
            session.add(hist)

            # Notification to farmer
            notif = Notification(
                user_id=farmer.id,
                title="Expert Response: Dr. Sunita Rao",
                message="Dr. Sunita Rao provided verified agronomic recommendations and precautions for your Paddy Case #1.",
                type="expert_response",
                link=f"/farmer/cases/{case.id}",
                is_read=False,
            )
            session.add(notif)

            # Notification to expert
            notif2 = Notification(
                user_id=expert_user.id,
                title="Case #1 Assigned and Resolved",
                message="You successfully reviewed and answered Case #1 for farmer Ramesh Kumar.",
                type="case_status",
                link=f"/expert/cases/{case.id}",
                is_read=True,
            )
            session.add(notif2)

            await session.commit()
            logger.info("Seeded demo agricultural consultation case #1 and notifications.")

    except Exception as ex:
        logger.warning(f"Notice while seeding expert and demo cases: {ex}")
        await session.rollback()
