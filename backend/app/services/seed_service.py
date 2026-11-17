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
]


async def seed_verified_agricultural_documents(session: AsyncSession) -> int:
    """
    Seeds verified agricultural guidance documents and precomputed vector embeddings
    if the database document table has no records.
    """
    try:
        count_res = await session.execute(select(func.count(Document.id)))
        existing_count = count_res.scalar() or 0

        if existing_count > 0:
            logger.info(f"Database already contains {existing_count} documents. Skipping initial seed.")
            return 0

        logger.info("Database empty. Seeding verified ICAR agricultural manuals & vector embeddings...")
        total_seeded = 0

        for doc_data in VERIFIED_SEED_DOCUMENTS:
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
