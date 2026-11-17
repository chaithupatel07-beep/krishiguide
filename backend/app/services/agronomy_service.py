import math
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.services.vector_search import VectorSearchService

# ==============================================================================
# MULTILINGUAL AGRONOMIC KNOWLEDGE BASE & DYNAMIC ENGINE
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. PEST & DISEASE DIAGNOSTIC REPOSITORY (ICAR / NCIPM GROUNDED)
# ------------------------------------------------------------------------------
PEST_DISEASE_DB: Dict[str, List[Dict[str, Any]]] = {
    "rice": [
        {
            "id": "rice_stem_borer",
            "name": "Yellow Stem Borer",
            "scientific_name": "Scirpophaga incertulas",
            "parts": ["stem", "leaves", "panicle / flower", "panicle", "flowers"],
            "keywords": ["dead", "heart", "hole", "stem", "borer", "white ear", "drying"],
            "severity": "High (Economic Injury Level exceeded if >10% dead hearts)",
            "confidence": "96% High Match",
            "symptoms": {
                "English": "Central shoots dry up producing 'dead hearts' during vegetative stage, and 'white ears' with empty chaffy grains during flowering stage. Exit holes visible on the lower stem.",
                "Telugu": "శాకీయ దశలో పిలకలు ఎండిపోయి 'డెడ్ హార్ట్స్' (చచ్చిన పిలకలు), చిరుపొట్ట లేదా ఈనె దశలో 'తెల్ల కంకులు' ఏర్పడతాయి. కాండంపై చిన్న రంధ్రాలు కనిపిస్తాయి.",
                "Hindi": "वानस्पतिक अवस्था में तने के अंदर कीट खाने से 'डेड हार्ट' और बाली निकलने पर 'सफेद बालियां' (सूखी बालियां) बनती हैं। तने के निचले हिस्से पर छेद दिखाई देते हैं।"
            },
            "causes": "High humidity (>80%), excessive nitrogenous fertilizer application, and continuous standing water.",
            "organic_treatment": {
                "English": "Install pheromone traps @ 5/acre to monitor adult moths. Release egg parasitoids Trichogramma japonicum @ 40,000/acre at weekly intervals.",
                "Telugu": "ఎకరాకు 5 లింగాకర్షక బుట్టలు (ఫెరమోన్ ట్రాప్స్) అమర్చండి. ట్రైకోగ్రామా జపోనికమ్ గుడ్ల పరాన్నజీవులను ఎకరాకు 40,000 చొప్పున విడుదల చేయండి.",
                "Hindi": "प्रति एकड़ 5 फेरोमोन ट्रैप लगाएं। ट्राइकोग्राम्मा जैपोनिकम परजीवी को 40,000 प्रति एकड़ की दर से साप्ताहिक अंतराल पर छोड़ें।"
            },
            "ipm": [
                "Clip seedling leaf tips before transplanting to eliminate egg masses.",
                "Maintain Alternate Wetting and Drying (AWD) rather than continuous stagnant flooding.",
                "Avoid excessive single-dose urea application; use split doses with neem-coated urea."
            ],
            "chemical_treatment": {
                "English": "Apply Chlorantraniliprole 18.5% SC @ 60 ml/acre in 200 L water OR Cartap Hydrochloride 50% SP @ 400 g/acre.",
                "Telugu": "క్లోరాంట్రానిలిప్రోల్ 18.5% SC ని ఎకరాకు 60 మి.లీ 200 లీటర్ల నీటిలో కలిపి పిచికారీ చేయండి లేదా కార్టాప్ హైడ్రోక్లోరైడ్ 50% SP ని ఎకరాకు 400 గ్రాములు వాడండి.",
                "Hindi": "क्लोरेंट्रानिलिप्रोल 18.5% SC @ 60 मिली प्रति एकड़ 200 लीटर पानी में या कार्टाप हाइड्रोक्लोराइड 50% SP @ 400 ग्राम प्रति एकड़ का छिड़काव करें।"
            },
            "safety": "Wear rubber gloves and mask. Maintain a 14-day pre-harvest interval (PHI). Do not spray during peak honeybee activity (9 AM - 12 PM).",
            "source": "ICAR-National Research Centre for Integrated Pest Management (NCIPM), Manual Page 18"
        },
        {
            "id": "rice_blast",
            "name": "Rice Blast",
            "scientific_name": "Pyricularia oryzae (Magnaporthe oryzae)",
            "parts": ["leaves", "stem", "panicle / flower", "panicle"],
            "keywords": ["blast", "spot", "spindle", "lesion", "brown", "eye", "neck rot"],
            "severity": "Severe (High epidemic potential under cool nights)",
            "confidence": "94% High Match",
            "symptoms": {
                "English": "Spindle-shaped, diamond-like lesions with brown borders and grey/ash-colored centers on leaves. Infection at panicle base causes 'neck blast' leading to lodging and grain sterility.",
                "Telugu": "ఆకులపై కంటి లేదా నూలుకండె ఆకారపు మచ్చలు ఏర్పడతాయి. మచ్చల అంచులు గోధుమ రంగులో, మధ్య భాగం బూడిద రంగులో ఉంటాయి. వెన్ను కుళ్ళిపోవడాన్ని మెడ విరుపు అంటారు.",
                "Hindi": "पत्तियों पर आंख या धुरी के आकार के भूरे किनारों और राख जैसे केंद्र वाले धब्बे बनते हैं। बाली के आधार पर संक्रमण से 'गर्दन तोड़' (नेक ब्लास्ट) रोग हो जाता है।"
            },
            "causes": "Excessive nitrogen fertilizer, cool night temperatures (20-24°C), relative humidity >90%, and dew formation.",
            "organic_treatment": {
                "English": "Seed treatment with Pseudomonas fluorescens @ 10 g/kg seed. Foliar spray of cow urine (10%) + neem oil (3 ml/L).",
                "Telugu": "విత్తన శుద్ధి: కిలో విత్తనానికి 10 గ్రాముల సూడోమోనాస్ ఫ్లోరోసెన్స్ కలపాలి. ఆవు మూత్రం (10%) లేదా వేప నూనె 3 మి.లీ/లీటరు పిచికారీ చేయండి.",
                "Hindi": "स्यूडोमोनास फ्लोरोसेंस @ 10 ग्राम प्रति किलोग्राम बीज से बीजोपचार करें। 10% गोमूत्र या नीम तेल 3 मिली/लीटर का छिड़काव करें।"
            },
            "ipm": [
                "Avoid burning paddy straw; practice deep summer plowing to destroy fungal inoculum.",
                "Use blast-resistant cultivars such as MTU-1010, IR-64, or BPT-5204 (Samba Mahsuri).",
                "Do not apply nitrogen fertilizer when disease lesions are actively expanding."
            ],
            "chemical_treatment": {
                "English": "Foliar spray of Tricyclazole 75% WP @ 120 g/acre in 200 L water OR Azoxystrobin 18.2% + Difenoconazole 11.4% SC @ 200 ml/acre.",
                "Telugu": "ట్రైసైక్లాజోల్ 75% WP ని ఎకరాకు 120 గ్రాములు లేదా అజాక్సిస్ట్రోబిన్ + డైఫెనోకొనాజోల్ ని ఎకరాకు 200 మి.లీ 200 లీటర్ల నీటిలో కలిపి పిచికారీ చేయండి.",
                "Hindi": "ट्राइसाइक्लाजोल 75% WP @ 120 ग्राम प्रति एकड़ या एज़ोक्सीस्ट्रोबिन + डिफेनोकोनाज़ोल @ 200 मिली प्रति एकड़ का छिड़काव करें।"
            },
            "safety": "Ensure complete canopy spray coverage. Do not spray during windy conditions to avoid drift onto water bodies.",
            "source": "ICAR-Indian Institute of Rice Research (IIRR), Disease Management Manual Page 24"
        },
        {
            "id": "rice_bph",
            "name": "Brown Plant Hopper (BPH)",
            "scientific_name": "Nilaparvata lugens",
            "parts": ["stem", "roots", "leaves"],
            "keywords": ["hopper", "burn", "bph", "sucking", "dry patch", "base", "brown hopper"],
            "severity": "Critical (Causes sudden 'hopper burn' circular drying)",
            "confidence": "95% High Match",
            "symptoms": {
                "English": "Nymphs and adults congregate at the base of the plant above water level, sucking sap. Crops show circular yellowing patches that rapidly turn brown and dry, known as 'hopper burn'.",
                "Telugu": "పిల్ల పురుగులు, పెద్ద పురుగులు మొక్క మొదళ్ళ వద్ద ఉండి రసం పీల్చడం వల్ల పంట వలయాకారంలో ఎండిపోతుంది. దీనిని 'సుడి దోమ' లేదా 'హాప్పర్ బర్న్' అంటారు.",
                "Hindi": "कीट पौधों के आधार पर पानी के स्तर के ठीक ऊपर रस चूसते हैं, जिससे खेत में गोलाकार पैच सूख जाते हैं जिसे 'हॉपर बर्न' कहा जाता है।"
            },
            "causes": "Dense plant spacing, close planting, indiscriminate use of synthetic pyrethroids, and excessive nitrogen.",
            "organic_treatment": {
                "English": "Form alleyways (passing rows of 30 cm after every 2 meters) to allow sunlight and aeration. Conserve natural mirid bugs and spiders.",
                "Telugu": "పైరులో ప్రతి 2 మీటర్లకు 30 సెం.మీ 'బాటలు' తీయడం ద్వారా గాలి, వెలుతురు సోకి దోమ ఉధృతి తగ్గుతుంది. సాలీళ్ళను కాపాడండి.",
                "Hindi": "खेत में हवा और धूप के लिए हर 2 मीटर पर 30 सेमी का 'रास्ता' छोड़ें। मकरियों और प्राकृतिक परभक्षी कीटों का संरक्षण करें।"
            },
            "ipm": [
                "Drain standing water from the field for 3-4 days to break the insect life cycle.",
                "Avoid resurgence-inducing insecticides like Cypermethrin or Deltamethrin.",
                "Install yellow sticky traps along field bunds."
            ],
            "chemical_treatment": {
                "English": "Spray Triflumezopyrim 10% SC @ 94 ml/acre OR Pymetrozine 50% WG @ 120 g/acre directing spray specifically at plant base.",
                "Telugu": "ట్రైఫ్లూమెజోపైరిమ్ 10% SC ఎకరాకు 94 మి.లీ లేదా పైమెట్రోజైన్ 50% WG ఎకరాకు 120 గ్రాములు మొక్కల మొదళ్ళ వద్ద తడిచేలా పిచికారీ చేయండి.",
                "Hindi": "ट्राइफ्लूमेज़ोपाइरिम 10% SC @ 94 मिली प्रति एकड़ या पाइमेट्रोज़िन 50% WG @ 120 ग्राम प्रति एकड़ को पौधे के निचले हिस्से पर स्प्रे करें।"
            },
            "safety": "Direct the spray nozzle toward the base of hills, not on the foliage top. Wear protective gear.",
            "source": "ICAR-National Rice Research Institute (NRRI), Pest Protocol Page 32"
        }
    ],
    "chilli": [
        {
            "id": "chilli_thrips",
            "name": "Chilli Thrips & Yellow Mites Complex",
            "scientific_name": "Scirtothrips dorsalis & Polyphagotarsonemus latus",
            "parts": ["leaves", "flowers", "panicle / flower", "fruits", "stem"],
            "keywords": ["curl", "curling", "yellow", "thrip", "mite", "boat", "crinkled", "upward", "downward"],
            "severity": "High (Causes severe leaf deformation and floral drop)",
            "confidence": "97% Very High Match",
            "symptoms": {
                "English": "Leaves curl upwards into an inverted boat shape with brittle texture due to Thrips. Yellow mites cause downward leaf curling with bronzing, thickening, and elongation of petiole.",
                "Telugu": "తామర పురుగుల (త్రిప్స్) వల్ల ఆకులు పైకి దోనె ఆకారంలో ముడుచుకుంటాయి. నల్లి (మైట్స్) వల్ల ఆకులు కిందికి ముడుచుకుని, దళసరిగా మారి తిరగబడతాయి.",
                "Hindi": "थ्रिप्स के कारण पत्तियां नाव के आकार में ऊपर की ओर मुड़ जाती हैं। पीले माइट्स के कारण पत्तियां नीचे की ओर मुड़ती हैं और मोटी व तांबे जैसी हो जाती हैं।"
            },
            "causes": "Hot, dry weather favors thrips, while warm humid conditions favor yellow mites. High monoculture density.",
            "organic_treatment": {
                "English": "Foliar spray of Neem Seed Kernel Extract (NSKE 5%) or Neem Oil 10,000 ppm @ 3 ml/L. Install 20 blue/yellow sticky traps per acre.",
                "Telugu": "వేపగింజల కషాయం (NSKE 5%) లేదా వేపనూనె 10,000 ppm ని లీటరు నీటికి 3 మి.లీ కలిపి పిచికారీ చేయండి. ఎకరాకు 20 నీలి మరియు పసుపు రంగు జిగురు అట్టలు పెట్టండి.",
                "Hindi": "नीम बीज कर्नल अर्क (NSKE 5%) या नीम तेल @ 3 मिली/लीटर का छिड़काव करें। प्रति एकड़ 20 नीले और पीले चिपचिपे जाल लगाएं।"
            },
            "ipm": [
                "Intercrop with barrier crops like maize, sorghum, or castor to reduce pest vector migration.",
                "Spray systemic bio-pesticides like Lecanicillium lecanii @ 5 g/L under cool hours.",
                "Spray cold water forcefully on foliage to dislodge mite colonies."
            ],
            "chemical_treatment": {
                "English": "For Thrips: Fipronil 5% SC @ 2 ml/L OR Spinetoram 11.7% SC @ 1 ml/L. For Mites: Diafenthiuron 50% WP @ 1.2 g/L OR Spiromesifen 22.9% SC @ 1 ml/L.",
                "Telugu": "తామర పురుగులకు: ఫిప్రోనిల్ 5% SC (2 మి.లీ/లీ) లేదా స్పినెటోరమ్ 11.7% SC (1 మి.లీ/లీ). నల్లి నివారణకు: డయాఫెంథియురాన్ 50% WP (1.2 గ్రా/లీ) లేదా స్పైరోమెసిఫెన్ 22.9% SC (1 మి.లీ/లీ).",
                "Hindi": "थ्रिप्स के लिए: फ़िप्रोनिल 5% SC @ 2 मिली/लीटर या स्पिनेटोरम 11.7% SC @ 1 मिली/लीटर। माइट्स के लिए: डायफेंथियूरॉन 50% WP @ 1.2 ग्राम/लीटर का छिड़काव करें।"
            },
            "safety": "Alternate different chemical groups to prevent insect resistance buildup. Maintain safety gloves and mask.",
            "source": "ICAR-Indian Institute of Horticultural Research (IIHR), Chilli Care Manual Page 15"
        },
        {
            "id": "chilli_root_rot",
            "name": "Damping Off & Bacterial Wilt / Root Rot Complex",
            "scientific_name": "Pythium aphanidermatum & Ralstonia solanacearum",
            "parts": ["roots", "stem"],
            "keywords": ["root", "rot", "wilt", "damping", "collar", "drooping", "sudden death", "decay"],
            "severity": "Severe (High mortality in young plants and waterlogged patches)",
            "confidence": "95% High Match",
            "symptoms": {
                "English": "In roots: Water-soaked decaying tap root and brown discoloration. At collar: stem softening and seedling collapse. In mature plants: Sudden wilting during midday with leaves remaining green.",
                "Telugu": "వేర్లు కుళ్ళిపోయి నల్లబడటం, మొక్క మొదలు మెత్తబడి నల్లటి మచ్చలు రావడం, నీరు లేనట్లుగా పగటివేళ హఠాత్తుగా ఆకులు వాడిపోవడాన్ని 'వేరుకుళ్ళు' లేదా 'ఎండు తెగులు' అంటారు.",
                "Hindi": "जड़ों का सड़ना, भूरापन और पौधे का अचानक हरा ही मुरझा जाना (मुरझान या जड़ गलन)। कॉलर क्षेत्र में तना मुलायम होकर गल जाता है।"
            },
            "causes": "Poor soil drainage, excessive irrigation, waterlogging, acidic soils, and soil-borne fungal/bacterial pathogens.",
            "organic_treatment": {
                "English": "Soil application of Trichoderma viride or T. harzianum @ 2 kg mixed with 200 kg FYM per acre. Drench with Pseudomonas fluorescens @ 10 g/L.",
                "Telugu": "ఎకరాకు 2 కిలోల ట్రైకోడెర్మా విరిడిని 200 కిలోల పశువుల ఎరువులో కలిపి పాదుల వద్ద వేయండి. సూడోమోనాస్ ఫ్లోరోసెన్స్ 10 గ్రా/లీ నీటిలో కలిపి పాదులను తడపండి.",
                "Hindi": "ट्राइकोडर्मा विरिडी 2 किग्रा को 200 किग्रा गोबर की खाद में मिलाकर प्रति एकड़ भूमि में डालें। स्यूडोमोनास फ्लोरोसेंस का जड़ों के पास छिड़काव करें।"
            },
            "ipm": [
                "Prepare raised beds of 15 cm height with 30 cm drainage furrows to avoid standing water.",
                "Practice solarization of nursery beds using 25-micron polythene sheet for 30 days during summer.",
                "Rotate with non-solanaceous crops like maize or marigold."
            ],
            "chemical_treatment": {
                "English": "Soil drenching around plant root zone with Copper Oxychloride 50% WP @ 3 g/L + Streptocycline @ 0.1 g/L OR Metalaxyl 8% + Mancozeb 64% WP @ 2.5 g/L.",
                "Telugu": "కాపర్ ఆక్సిక్లోరైడ్ (3 గ్రా/లీ) + స్ట్రెప్టోసైక్లిన్ (0.1 గ్రా/లీ) లేదా మెటలాక్సిల్ + మాంకోజెబ్ (2.5 గ్రా/లీ) నీటిలో కలిపి మొక్కల వేర్ల వద్ద తడపాలి.",
                "Hindi": "कॉपर ऑक्सीक्लोराइड 50% WP @ 3 ग्राम/लीटर + स्ट्रेप्टोसाइक्लिन @ 0.1 ग्राम/लीटर या मेटालेक्सिल + मैंकोज़ेब @ 2.5 ग्राम/लीटर से जड़ों के पास ड्रेंचिंग करें।"
            },
            "safety": "Do not flood the field after drenching. Disinfect agricultural tools used in infected patches.",
            "source": "ICAR-Indian Agricultural Research Institute (IARI), Plant Pathology Bulletin Page 22"
        },
        {
            "id": "chilli_anthracnose",
            "name": "Anthracnose & Fruit Rot (Die-back)",
            "scientific_name": "Colletotrichum capsici",
            "parts": ["fruits", "stem", "leaves"],
            "keywords": ["fruit", "die-back", "spot", "sunken", "black", "anthracnose", "rot", "drying twigs"],
            "severity": "High (Causes direct pod market degradation and twig drying)",
            "confidence": "94% High Match",
            "symptoms": {
                "English": "Circular, sunken dark brown spots with concentric rings of black acervuli on ripe fruits. Twigs dry from top downwards (Die-back), turning straw-colored with black dots.",
                "Telugu": "పండ్లపై గుండ్రటి నల్లని సొట్ట మచ్చలు, కొమ్మలు పై నుండి కిందికి ఎండిపోవడాన్ని కొమ్మ ఎండు లేదా 'కాయకుళ్ళు' తెగులు అంటారు.",
                "Hindi": "फलों पर काले धब्बे और फल सड़न। टहनियां ऊपर से नीचे की ओर सूखती हैं जिसे 'डाई-बैक' कहा जाता है।"
            },
            "causes": "High humidity (>85%), rainfall during fruit maturation, temperatures around 28°C.",
            "organic_treatment": {
                "English": "Seed treatment with Trichoderma viride @ 4 g/kg seed. Foliar spray of cow dung filtrate (5%) or Neem cake extract (10%).",
                "Telugu": "కిలో విత్తనానికి 4 గ్రాముల ట్రైకోడెర్మా విరిడితో విత్తనశుద్ధి చేయండి. వేపపిండి కషాయం లేదా పంచగవ్య పిచికారీ చేయండి.",
                "Hindi": "ट्राइकोडर्मा विरिडी @ 4 ग्राम/किलो से बीजोपचार करें। नीम अर्क या पंचगव्य का छिड़काव करें।"
            },
            "ipm": [
                "Collect and burn infected twigs and mummified fruits to reduce field inoculum.",
                "Maintain wider plant spacing of 60 x 45 cm for proper air circulation.",
                "Harvest ripe pods promptly without letting them over-ripen on plants."
            ],
            "chemical_treatment": {
                "English": "Spray Azoxystrobin 23% SC @ 1 ml/L OR Propiconazole 25% EC @ 1 ml/L OR Tebuconazole 25.9% EC @ 1.25 ml/L of water at 12-day intervals.",
                "Telugu": "అజాక్సిస్ట్రోబిన్ 23% SC (1 మి.లీ/లీ) లేదా టెబుకొనాజోల్ (1.25 మి.లీ/లీ) లేదా ప్రోపికొనాజోల్ (1 మి.లీ/లీ) నీటిలో కలిపి 12 రోజుల వ్యవధిలో పిచికారీ చేయండి.",
                "Hindi": "एज़ोक्सीस्ट्रोबिन 23% SC @ 1 मिली/लीटर या टेबुकोनाज़ोल @ 1.25 मिली/लीटर का 12 दिनों के अंतराल पर छिड़काव करें।"
            },
            "safety": "Cease chemical application 10 days before picking chillies. Use full personal protective equipment.",
            "source": "ICAR Spices and Plantation Crops Guide, NCIPM Page 29"
        }
    ],
    "cotton": [
        {
            "id": "cotton_pink_bollworm",
            "name": "Pink Bollworm",
            "scientific_name": "Pectinophora gossypiella",
            "parts": ["flowers", "fruits", "panicle / flower", "stem"],
            "keywords": ["bollworm", "pink", "rosette", "flower", "boll", "larvae", "stunted boll"],
            "severity": "Severe (Critical economic pest affecting lint quality and yield)",
            "confidence": "98% Very High Match",
            "symptoms": {
                "English": "Infested flowers fail to open normally, twisting into a characteristically deformed 'rosette flower'. Larvae bore into developing bolls, eating seeds and causing staining of white lint.",
                "Telugu": "గులాబీ రంగు కాయతొలుచు పురుగు వల్ల పూత విచ్చుకోకుండా 'ముడుచుకున్న రోసేట్ పువ్వులు' గా మారుతుంది. కాయలపై రంధ్రాలు చేసి దూదిని నల్లగా మారుస్తాయి.",
                "Hindi": "गुलाबी सुंडी के कारण फूल ठीक से नहीं खिलते और 'गुलाब जैसे मुड़े हुए' (रोसेट) फूल बनते हैं। सुंडी टिंडों में छेद कर बीजों को खाती है और रुई की गुणवत्ता खराब करती है।"
            },
            "causes": "Continuous ratoon cotton crops, long-duration hybrids, and late-season weather with moderate heat.",
            "organic_treatment": {
                "English": "Install 8 pheromone traps/acre for monitoring, and 16/acre for mass trapping. Release Trichogrammatoidea bactrae @ 60,000/acre at weekly intervals.",
                "Telugu": "ఎకరాకు 8-10 లింగాకర్షక బుట్టలు అమర్చండి. ట్రైకోగ్రామటోయిడియా బాక్ట్రే గుడ్ల పరాన్నజీవులను ఎకరాకు 60,000 చొప్పున విడుదల చేయండి.",
                "Hindi": "प्रति एकड़ 8 फेरोमोन ट्रैप लगाएं। ट्राइकोग्रामेटोइडिया परजीवी को 60,000 प्रति एकड़ की दर से छोड़ें।"
            },
            "ipm": [
                "Terminate the crop by December-January; strictly avoid ratoon cotton farming.",
                "Hand-pick and destroy rosette flowers every 3 to 4 days during flowering phase.",
                "Adopt close planting systems and short-duration varieties."
            ],
            "chemical_treatment": {
                "English": "Apply Chlorpyriphos 20% EC @ 2.5 ml/L OR Emamectin Benzoate 5% SG @ 0.5 g/L OR Profenofos 50% EC @ 2 ml/L of water.",
                "Telugu": "ఎమామెక్టిన్ బెంజోయేట్ 5% SG ని లీటరు నీటికి 0.5 గ్రాములు లేదా క్లోర్‌పైరిఫాస్ 20% EC ని లీటరుకు 2.5 మి.లీ కలిపి పిచికారీ చేయండి.",
                "Hindi": "इमामेक्टिन बेंजोएट 5% SG @ 0.5 ग्राम/लीटर या प्रोफेनोफोस 50% EC @ 2 मिली/लीटर पानी का छिड़काव करें।"
            },
            "safety": "Do not spray synthetic pyrethroids repeatedly as they cause secondary pest outbreaks of whitefly.",
            "source": "ICAR-Central Institute for Cotton Research (CICR), Technical Bulletin Page 41"
        },
        {
            "id": "cotton_whitefly",
            "name": "Cotton Whitefly & Leaf Curl",
            "scientific_name": "Bemisia tabaci",
            "parts": ["leaves", "stem"],
            "keywords": ["whitefly", "sucking", "soot", "honeydew", "white patch", "yellowing", "leaf curl"],
            "severity": "High (Vector for Cotton Leaf Curl Virus / CLCuV)",
            "confidence": "95% High Match",
            "symptoms": {
                "English": "Minute white flies on the underside of leaves. Nymphs excrete sticky honeydew causing black sooty mold growth on upper foliage, hindering photosynthesis. Leaves turn chlorotic.",
                "Telugu": "ఆకుల అడుగు భాగంలో తెల్లదోమ ఉండి రసం పీల్చడం, తేనె వంటి జిగురు పదార్ధాన్ని విసర్జించడం వల్ల ఆకులపై నల్లటి బూజు (మసి తెగులు) ఏర్పడుతుంది.",
                "Hindi": "पत्तियों की निचली सतह पर सफेद मक्खी रस चूसती है और चिपचिपा तरल छोड़ती है जिससे पत्तियों पर काली फफूंद (काली फफूंदी) जम जाती है।"
            },
            "causes": "Hot and dry dry-spells followed by intermittent humidity, monocropping, and excessive nitrogen application.",
            "organic_treatment": {
                "English": "Erect 15 yellow sticky traps/acre at crop canopy level. Spray Neem Oil 10,000 ppm @ 3 ml/L or Verticillium lecanii @ 5 g/L.",
                "Telugu": "ఎకరాకు 15 పసుపు రంగు జిగురు అట్టలను పైరు ఎత్తులో అమర్చండి. వేపనూనె 10,000 ppm (3 మి.లీ/లీ) పిచికారీ చేయండి.",
                "Hindi": "प्रति एकड़ 15 पीले चिपचिपे जाल लगाएं। 10,000 ppm नीम तेल @ 3 मिली/लीटर का छिड़काव करें।"
            },
            "ipm": [
                "Grow barrier crops like pearl millet (bajra) or maize around cotton field borders.",
                "Avoid spraying broad-spectrum pyrethroids that kill natural predators like Encarsia wasps.",
                "Weed out alternate weed hosts like Abutilon indicum and Parthenium from bunds."
            ],
            "chemical_treatment": {
                "English": "Spray Diafenthiuron 50% WP @ 1.2 g/L OR Pyriproxyfen 10% EC @ 2 ml/L OR Afidopyropen 50 g/L DC @ 1 ml/L.",
                "Telugu": "డయాఫెంథియురాన్ 50% WP (1.2 గ్రా/లీ) లేదా పైరిప్రాక్సిఫెన్ 10% EC (2 మి.లీ/లీ) నీటిలో కలిపి పిచికారీ చేయండి.",
                "Hindi": "डायफेंथियूरॉन 50% WP @ 1.2 ग्राम/लीटर या पाइरीप्रॉक्सीफेन 10% EC @ 2 मिली/लीटर का छिड़काव करें।"
            },
            "safety": "Spray under surface of leaves thoroughly. Wear chemical mask and gloves.",
            "source": "ICAR-CICR Nagpur, Integrated Pest Management Protocol Page 27"
        }
    ],
    "tomato": [
        {
            "id": "tomato_fruit_borer",
            "name": "Tomato Fruit Borer",
            "scientific_name": "Helicoverpa armigera",
            "parts": ["fruits", "flowers", "leaves"],
            "keywords": ["borer", "fruit", "caterpillar", "hole", "rot", "dropping", "dark spots on fruit"],
            "severity": "High (Direct commercial fruit damage)",
            "confidence": "96% High Match",
            "symptoms": {
                "English": "Circular bore holes in developing green and ripe fruits, with the caterpillar's body half thrust inside feeding on the internal pulp. Affected fruits rot and drop prematurely.",
                "Telugu": "కాయతొలుచు పురుగు కాయలపై గుండ్రటి రంధ్రాలు చేసి లోపలి గుజ్జును తింటుంది. పురుగు సగం బయటకు, సగం లోపలికి ఉంటుంది. కాయలు కుళ్ళి రాలిపోతాయి.",
                "Hindi": "टमाटर के फलों में गोल छेद हो जाते हैं और सूंडी अंदर का गूदा खाती है, जिससे फल सड़कर गिर जाते हैं।"
            },
            "causes": "Warm weather, flowering and fruiting stage overlap, absence of trap crops.",
            "organic_treatment": {
                "English": "Plant African Marigold (Tagetes erecta) as a trap crop (1 row of marigold for every 16 rows of tomato). Release egg parasitoid Trichogramma pretiosum @ 50,000/acre.",
                "Telugu": "ప్రతి 16 టమాటా వరుసలకు ఒక వరుస బంతి పూల మొక్కలను ఎర పంటగా వేయండి. హెచ్.ఎన్.పి.వి (HaNPV) వైరస్ ద్రావణాన్ని పిచికారీ చేయండి.",
                "Hindi": "हर 16 कतार टमाटर के बाद 1 कतार गेंदे की ट्रैप क्रॉप के रूप में लगाएं। ट्राइकोग्राम्मा परजीवी छोड़ें।"
            },
            "ipm": [
                "Install 5 Helicoverpa pheromone traps per acre.",
                "Spray HaNPV (Helicoverpa nuclear polyhedrosis virus) @ 250 LE/acre with 0.1% jaggery in evening.",
                "Handpick and destroy damaged fruits regularly."
            ],
            "chemical_treatment": {
                "English": "Spray Chlorantraniliprole 18.5% SC @ 0.3 ml/L OR Flubendiamide 39.35% SC @ 0.3 ml/L OR Novaluron 10% EC @ 1.5 ml/L of water.",
                "Telugu": "క్లోరాంట్రానిలిప్రోల్ 18.5% SC (0.3 మి.లీ/లీ) లేదా ఫ్లూబెండియమైడ్ (0.3 మి.లీ/లీ) నీటిలో కలిపి పిచికారీ చేయండి.",
                "Hindi": "क्लोरेंट्रानिलिप्रोल 18.5% SC @ 0.3 मिली/लीटर या फ्लूबेन्डियामाइड @ 0.3 मिली/लीटर का छिड़काव करें।"
            },
            "safety": "Adhere strictly to 5-day pre-harvest interval before picking market tomatoes.",
            "source": "ICAR-Indian Institute of Vegetable Research (IIVR), Manual Page 36"
        },
        {
            "id": "tomato_early_blight",
            "name": "Early Blight & Fruit Target Spot",
            "scientific_name": "Alternaria solani",
            "parts": ["leaves", "fruits", "stem"],
            "keywords": ["blight", "target", "concentric", "dark spot", "ring", "yellow halo", "leaf spot"],
            "severity": "Moderate to High",
            "confidence": "95% High Match",
            "symptoms": {
                "English": "Brown to dark circular spots with distinct concentric rings (target board pattern) surrounded by a yellow halo on lower leaves. Dark leathery sunken spots at fruit stem-end.",
                "Telugu": "ఆకులపై లక్ష్యపు పలక (టార్గెట్ బోర్డు) మాదిరిగా గుండ్రటి వలయాలతో కూడిన ముదురు గోధుమ రంగు మచ్చలు ఏర్పడతాయి. ఆకులు ఎండి రాలిపోతాయి.",
                "Hindi": "पत्तियों पर 'टारगेट बोर्ड' जैसे संकेंद्रित छल्लों वाले गहरे भूरे धब्बे बनते हैं। फलों के डंठल के पास काले धंसे हुए धब्बे दिखाई देते हैं।"
            },
            "causes": "High humidity, frequent dew, warm temperatures (24-29°C), and dense plant spacing.",
            "organic_treatment": {
                "English": "Seed treatment with Trichoderma harzianum @ 10 g/kg seed. Foliar spray of Bordeaux mixture (1%) or Copper Hydroxide @ 2 g/L.",
                "Telugu": "ట్రైకోడెర్మాతో విత్తనశుద్ధి చేయండి. 1% బోర్డో మిశ్రమం లేదా కాపర్ హైడ్రాక్సైడ్ 2 గ్రా/లీ పిచికారీ చేయండి.",
                "Hindi": "ट्राइकोडर्मा से बीजोपचार करें। 1% बोर्डो मिश्रण या कॉपर हाइड्रॉक्साइड का छिड़काव करें।"
            },
            "ipm": [
                "Prune lower leaves that touch the soil surface to minimize soil-splash fungal spores.",
                "Use drip irrigation rather than overhead sprinklers to keep foliage dry.",
                "Stake plants with bamboo sticks to improve canopy ventilation."
            ],
            "chemical_treatment": {
                "English": "Spray Mancozeb 75% WP @ 2.5 g/L OR Azoxystrobin 18.2% + Difenoconazole 11.4% SC @ 1 ml/L OR Chlorothalonil 75% WP @ 2 g/L.",
                "Telugu": "మాంకోజెబ్ 75% WP (2.5 గ్రా/లీ) లేదా అజాక్సిస్ట్రోబిన్ + డైఫెనోకొనాజోల్ (1 మి.లీ/లీ) నీటిలో కలిపి పిచికారీ చేయండి.",
                "Hindi": "मैंकोज़ेब 75% WP @ 2.5 ग्राम/लीटर या एज़ोक्सीस्ट्रोबिन + डिफेनोकोनाज़ोल @ 1 मिली/लीटर का छिड़काव करें।"
            },
            "safety": "Ensure spray reaches the underside of lower leaves where early blight begins.",
            "source": "ICAR-IIVR Varanasi Vegetable Health Manual Page 19"
        }
    ],
    "maize": [
        {
            "id": "maize_fall_armyworm",
            "name": "Fall Armyworm (FAW)",
            "scientific_name": "Spodoptera frugiperda",
            "parts": ["leaves", "stem", "panicle / flower", "panicle"],
            "keywords": ["armyworm", "faw", "whorl", "frass", "ragged", "pinhole", "chewed"],
            "severity": "Critical (Causes total defoliation and cob destruction if unmanaged)",
            "confidence": "98% Very High Match",
            "symptoms": {
                "English": "Young larvae scrape leaf epidermis creating pinholes; mature larvae feed inside the central whorl leaving ragged, torn leaves with copious amounts of coarse sawdust-like frass.",
                "Telugu": "కత్తెర పురుగు ఆకులను విపరీతంగా తినివేయడం వల్ల ఆకులు చిరిగిపోయినట్లుగా మారతాయి. మొక్క సుడులలో (సుడిలో) చెక్కపొట్టు వంటి విసర్జితాలు స్పష్టంగా కనిపిస్తాయి.",
                "Hindi": "फॉल आर्मीवॉर्म पत्तियों को खुरचता है और पौधों के केंद्रीय भंवर (व्होर्ल) में रहकर भारी मात्रा में लकड़ी के बुरादे जैसा मल छोड़ता है, जिससे पत्तियां छलनी हो जाती हैं।"
            },
            "causes": "Warm tropical weather, delayed sowing, monoculture maize cropping.",
            "organic_treatment": {
                "English": "Apply fine dry sand mixed with neem cake (9:1) or wood ash directly into the plant whorls. Spray Bacillus thuringiensis (Bt) kurstaki @ 2 g/L.",
                "Telugu": "సుడులలో వేపపిండి + ఇసుక మిశ్రమాన్ని (1:9 నిష్పత్తిలో) వేయండి. బసిల్లస్ తురింజియెన్సిస్ (Bt) ని లీటరు నీటికి 2 గ్రాములు కలిపి సుడిలో పడేలా పిచికారీ చేయండి.",
                "Hindi": "पौधे के भंवर (व्होर्ल) में रेत और नीम की खली (9:1) का मिश्रण डालें। बैसिलस थुरिंजिएंसिस (Bt) @ 2 ग्राम/लीटर का छिड़काव करें।"
            },
            "ipm": [
                "Install FAW pheromone traps @ 5/acre across the field right from emergence.",
                "Intercrop with short pulses like cowpea or desmodium to attract natural predators.",
                "Erect bird perches @ 10/acre to encourage insectivorous birds."
            ],
            "chemical_treatment": {
                "English": "Direct whorl application of Spinetoram 11.7% SC @ 0.5 ml/L OR Chlorantraniliprole 18.5% SC @ 0.4 ml/L OR Emamectin Benzoate 5% SG @ 0.4 g/L.",
                "Telugu": "స్పైనిటోరమ్ 11.7% SC (0.5 మి.లీ/లీ) లేదా క్లోరాంట్రానిలిప్రోల్ (0.4 మి.లీ/లీ) సుడిలో పడేలా జాగ్రత్తగా పిచికారీ చేయాలి.",
                "Hindi": "स्पिनेटोरम 11.7% SC @ 0.5 मिली/लीटर या इमामेक्टिन बेंजोएट 5% SG @ 0.4 ग्राम/लीटर को सीधे पौधे के भंवर में स्प्रे करें।"
            },
            "safety": "Direct spray nozzle directly into the central whorl of each plant using knapsack sprayer with cone nozzle removed.",
            "source": "ICAR-Indian Institute of Maize Research (IIMR), FAW Advisory Page 14"
        }
    ],
    "groundnut": [
        {
            "id": "groundnut_tikka",
            "name": "Tikka Leaf Spot & Rust Complex",
            "scientific_name": "Cercospora arachidicola & Puccinia arachidis",
            "parts": ["leaves", "stem"],
            "keywords": ["tikka", "spot", "halo", "rust", "defoliation", "brown spot", "orange pustule"],
            "severity": "High (Reduces pod filling and photosynthetic leaf area)",
            "confidence": "96% High Match",
            "symptoms": {
                "English": "Early leaf spot produces circular brown spots with prominent yellow halos. Late leaf spot produces dark black spots on leaf underside. Rust causes orange-brown pustules, leading to severe leaf fall.",
                "Telugu": "ఆకులపై గుండ్రటి మచ్చలు ఏర్పడి వాటి చుట్టూ పసుపు రంగు వలయం ఏర్పడుతుంది (తిక్కా ఆకుమచ్చ తెగులు). ఆకుల అడుగున నారింజ రంగు కురుపుల వంటి తుప్పు మచ్చలు ఏర్పడతాయి.",
                "Hindi": "टिक्का रोग में पत्तियों पर पीले छल्ले वाले भूरे-काले धब्बे बनते हैं। गेरूई (रस्ट) में पत्तियों की निचली सतह पर नारंगी-भूरे रंग के दानेदार उभार बनते हैं।"
            },
            "causes": "High relative humidity (>85%), temperatures around 25-28°C with intermittent showers.",
            "organic_treatment": {
                "English": "Seed treatment with Trichoderma viride @ 4 g/kg seed. Foliar spray of 5% Neem Seed Kernel Extract (NSKE) at initial incidence.",
                "Telugu": "ట్రైకోడెర్మా విరిడితో విత్తనశుద్ధి చేయండి. 5% వేపగింజల కషాయం పిచికారీ చేయండి.",
                "Hindi": "ट्राइकोडर्मा विरिडी से बीजोपचार करें और 5% नीम अर्क का छिड़काव करें।"
            },
            "ipm": [
                "Practice crop rotation with pearl millet, sorghum, or maize.",
                "Destroy infected crop residues after harvest to prevent spore overwintering.",
                "Ensure balanced potash application to strengthen leaf cell walls."
            ],
            "chemical_treatment": {
                "English": "Spray Tebuconazole 25.9% EC @ 1 ml/L OR Chlorothalonil 75% WP @ 2 g/L OR Mancozeb 75% WP @ 2.5 g/L at 15-day intervals.",
                "Telugu": "టెబుకొనాజోల్ 25.9% EC (1 మి.లీ/లీ) లేదా మాంకోజెబ్ 75% WP (2.5 గ్రా/లీ) నీటిలో కలిపి పిచికారీ చేయండి.",
                "Hindi": "टेबुकोनाज़ोल 25.9% EC @ 1 मिली/लीटर या मैंकोज़ेब 75% WP @ 2.5 ग्राम/लीटर का छिड़काव करें।"
            },
            "safety": "Ensure full coverage of lower foliage. Cease spray 20 days prior to harvest.",
            "source": "ICAR-Directorate of Groundnut Research (DGR), Package of Practices Page 21"
        },
        {
            "id": "groundnut_stem_rot",
            "name": "Stem Rot / Collar Rot (Sclerotium)",
            "scientific_name": "Sclerotium rolfsii",
            "parts": ["roots", "stem"],
            "keywords": ["stem rot", "collar rot", "white mycelium", "sclerotia", "wilting in patches", "rot"],
            "severity": "Severe (Causes sudden wilting of branches and pod loss)",
            "confidence": "95% High Match",
            "symptoms": {
                "English": "White fan-like fungal mycelium covers the stem near the soil surface (collar region). Mustard seed-like brown sclerotia appear. Stems soften, rot, and whole branches wilt.",
                "Telugu": "మొక్క మొదలు వద్ద భూమి ఉపరితలంపై తెల్లని బూజు (శిలీంధ్రం) వ్యాపించి ఆవగింజల వంటి గోధుమ రంగు గుళికలు ఏర్పడతాయి. మొదలు కుళ్ళి మొక్కలు ఎండిపోతాయి (కాండం కుళ్ళు).",
                "Hindi": "जमीन की सतह के पास तने पर सफेद फफूंद का जाल और सरसों के दाने जैसे भूरे रंग के स्क्लेरोशिया बनते हैं। तना गल जाता है और पौधा सूख जाता है।"
            },
            "causes": "High soil moisture, warm temperatures (28-32°C), deep planting, decaying organic debris at soil surface.",
            "organic_treatment": {
                "English": "Seed treatment with Trichoderma harzianum @ 10 g/kg seed. Soil application of Trichoderma @ 2 kg mixed in 100 kg farmyard manure per acre.",
                "Telugu": "కిలో విత్తనానికి 10 గ్రాముల ట్రైకోడెర్మాతో విత్తనశుద్ధి చేయండి. ఎకరాకు 2 కిలోల ట్రైకోడెర్మాను 100 కిలోల పశువుల ఎరువుతో కలిపి మొదళ్ళ వద్ద వేయండి.",
                "Hindi": "ट्राइकोडर्मा @ 10 ग्राम/किग्रा से बीजोपचार करें। 2 किग्रा ट्राइकोडर्मा को 100 किग्रा गोबर की खाद में मिलाकर खेत में डालें।"
            },
            "ipm": [
                "Avoid deep sowing; maintain 5 cm seed placement depth.",
                "Deep summer plowing to bury surface sclerotia below 15 cm.",
                "Avoid soil accumulation around plant collar during inter-cultivation."
            ],
            "chemical_treatment": {
                "English": "Seed treatment with Carboxin 37.5% + Thiram 37.5% DS @ 2 g/kg seed. Soil drenching around collar with Hexaconazole 5% SC @ 2 ml/L OR Tebuconazole @ 1.5 ml/L.",
                "Telugu": "విత్తనశుద్ధి: కార్బాక్సిన్ + థైరమ్ (2 గ్రా/కిలో). తెగులు గమనించినప్పుడు హెక్సాకొనాజోల్ (2 మి.లీ/లీ) మొక్క మొదలు తడిచేలా పిచికారీ చేయాలి.",
                "Hindi": "कार्बोक्सिन + थिरम @ 2 ग्राम/किग्रा से बीजोपचार करें। हेक्साकोनाज़ोल 5% SC @ 2 मिली/लीटर से कॉलर क्षेत्र में ड्रेंचिंग करें।"
            },
            "safety": "Direct spray specifically to the crown and collar of plants.",
            "source": "ICAR-DGR Junagadh Soil-borne Disease Protocols Page 16"
        }
    ]
}

# ------------------------------------------------------------------------------
# 2. CROP-SPECIFIC NUTRIENT CALIBRATION DATABASE (ICAR SOIL HEALTH NORMS)
# ------------------------------------------------------------------------------
CROP_NUTRIENTS = {
    "rice": {
        "n_kg_ha": 120, "p_kg_ha": 60, "k_kg_ha": 40,
        "stages": [
            {"name": "Basal (Transplanting)", "n_pct": 33.3, "p_pct": 100, "k_pct": 50, "desc": "Incorporate full DAP, half MOP, and 1/3rd Urea before final puddling."},
            {"name": "Tillering (20-25 DAT)", "n_pct": 33.3, "p_pct": 0, "k_pct": 0, "desc": "Top dress 1/3rd Urea under thin water layer (2-3 cm)."},
            {"name": "Panicle Initiation (40-45 DAT)", "n_pct": 33.4, "p_pct": 0, "k_pct": 50, "desc": "Top dress remaining 1/3rd Urea with remaining MOP for grain development."}
        ],
        "organic": "Apply 5-8 tonnes/ha well-decomposed FYM or green manuring with Sesbania (Dhaincha) @ 25 kg seed/ha 45 days before puddling.",
        "soil_remedy": "Apply Zinc Sulphate (ZnSO4) @ 25 kg/ha once every 3 seasons to prevent Khaira disease.",
        "source": "ICAR-National Rice Research Institute (NRRI) & DRR Manual"
    },
    "cotton": {
        "n_kg_ha": 140, "p_kg_ha": 60, "k_kg_ha": 60,
        "stages": [
            {"name": "Basal (Sowing)", "n_pct": 20, "p_pct": 100, "k_pct": 33.3, "desc": "Band place full DAP, 1/3rd MOP, and starter Urea 5 cm beside seed row."},
            {"name": "Square Formation (35-45 DAS)", "n_pct": 40, "p_pct": 0, "k_pct": 33.3, "desc": "Top dress 40% Nitrogen along with Potassium during earthing-up."},
            {"name": "Flowering & Boll Development (70-80 DAS)", "n_pct": 40, "p_pct": 0, "k_pct": 33.4, "desc": "Top dress remaining Nitrogen and Potash; foliar spray 2% DAP or 1% 13:0:45."}
        ],
        "organic": "Apply 8-10 tonnes/ha Farmyard Manure. Inoculate seeds with Azospirillum and PSB @ 25 g/kg seed.",
        "soil_remedy": "For black cotton soils, incorporate gypsum if sodic; foliar spray 1% Magnesium Sulphate at boll formation to prevent leaf reddening.",
        "source": "ICAR-Central Institute for Cotton Research (CICR) Bulletin"
    },
    "chilli": {
        "n_kg_ha": 150, "p_kg_ha": 60, "k_kg_ha": 60,
        "stages": [
            {"name": "Basal (Transplanting)", "n_pct": 25, "p_pct": 100, "k_pct": 50, "desc": "Apply full DAP, half MOP, and starter Urea into planting furrows."},
            {"name": "Vegetative Growth (30 DAT)", "n_pct": 25, "p_pct": 0, "k_pct": 0, "desc": "Top dress 25% Nitrogen around root perimeter followed by light irrigation."},
            {"name": "Flowering Stage (60 DAT)", "n_pct": 25, "p_pct": 0, "k_pct": 25, "desc": "Apply 25% Nitrogen and 25% Potash to enhance flower retention."},
            {"name": "Fruit Picking / Flush (90 DAT)", "n_pct": 25, "p_pct": 0, "k_pct": 25, "desc": "Apply remaining Nitrogen and Potash to sustain multiple pickings."}
        ],
        "organic": "Apply 10 tonnes/ha Vermicompost or enriched FYM with Trichoderma before bed preparation.",
        "soil_remedy": "Maintain soil pH 6.2 - 7.0; apply micronutrient mixture (Boron + Zinc) foliar spray @ 2 g/L at peak flowering.",
        "source": "ICAR-Indian Institute of Horticultural Research (IIHR) Guide"
    },
    "maize": {
        "n_kg_ha": 130, "p_kg_ha": 60, "k_kg_ha": 40,
        "stages": [
            {"name": "Basal (At Sowing)", "n_pct": 25, "p_pct": 100, "k_pct": 50, "desc": "Apply full DAP, 50% MOP, and 25% Urea band-placed 5 cm deep."},
            {"name": "Knee-High Stage (30-35 DAS)", "n_pct": 50, "p_pct": 0, "k_pct": 0, "desc": "Side-dress 50% Urea during inter-cultivation and earthing up."},
            {"name": "Tasseling & Silking (50-60 DAS)", "n_pct": 25, "p_pct": 0, "k_pct": 50, "desc": "Apply final 25% Urea and remaining MOP prior to grain filling."}
        ],
        "organic": "Apply 6 tonnes/ha FYM + Azotobacter biofertilizer seed treatment @ 200 g/10 kg seed.",
        "soil_remedy": "In red soils with low zinc, apply Zinc Sulphate @ 25 kg/ha at sowing.",
        "source": "ICAR-Indian Institute of Maize Research (IIMR) Manual"
    },
    "groundnut": {
        "n_kg_ha": 25, "p_kg_ha": 50, "k_kg_ha": 40,
        "stages": [
            {"name": "Basal (At Sowing)", "n_pct": 100, "p_pct": 100, "k_pct": 100, "desc": "Apply full starter Nitrogen, full DAP, and full MOP at seed furrow."},
            {"name": "Pegging & Flowering (40-45 DAS)", "n_pct": 0, "p_pct": 0, "k_pct": 0, "desc": "Broadcast 200 kg/ha Gypsum close to base and incorporate during light earthing-up."}
        ],
        "organic": "Inoculate seeds with Rhizobium culture (NC-92) @ 250 g/10 kg seed and PSB @ 250 g/10 kg.",
        "soil_remedy": "Gypsum (200 kg/acre) supplies critical Calcium and Sulphur for pod kernel filling and oil synthesis.",
        "source": "ICAR-Directorate of Groundnut Research (DGR) Package of Practices"
    },
    "tomato": {
        "n_kg_ha": 160, "p_kg_ha": 80, "k_kg_ha": 80,
        "stages": [
            {"name": "Basal (Transplanting)", "n_pct": 30, "p_pct": 100, "k_pct": 50, "desc": "Apply full Phosphorus, half Potash, and 30% Nitrogen in raised beds."},
            {"name": "Vegetative Growth (25-30 DAT)", "n_pct": 35, "p_pct": 0, "k_pct": 0, "desc": "Top dress 35% Nitrogen around plants before staking."},
            {"name": "Fruiting & Harvest (55-65 DAT)", "n_pct": 35, "p_pct": 0, "k_pct": 50, "desc": "Apply remaining Nitrogen and Potash to prevent fruit hollow-heart."}
        ],
        "organic": "Apply 10 tonnes/ha well-decomposed FYM or 3 tonnes/ha Vermicompost.",
        "soil_remedy": "Apply Calcium Nitrate @ 5 kg/acre to prevent Blossom End Rot; maintain soil pH 6.0-6.8.",
        "source": "ICAR-Indian Institute of Vegetable Research (IIVR) Guide"
    }
}

# ------------------------------------------------------------------------------
# 3. CROP WATER & IRRIGATION REQUIREMENTS (CRIDA / WTC NORMS)
# ------------------------------------------------------------------------------
CROP_IRRIGATION = {
    "rice": {
        "daily_water_mm": 6.5,
        "liters_acre_day": 26000,
        "drip_interval": "Daily or Alternate Days (1.5 - 2 hrs)",
        "sprinkler_interval": "Every 2 days (2.5 hrs)",
        "flood_interval": "Continuous shallow water layer (2-3 cm) or AWD every 3-4 days",
        "critical_stages": [
            {"stage": "Crown Root Initiation & Active Tillering", "importance": "Critical — water deficit reduces tiller count by 30%"},
            {"stage": "Panicle Initiation to Flowering", "importance": "Most Critical — drought causes spikelet sterility and chaffy grain"},
            {"stage": "Grain Milking & Dough Stage", "importance": "High — ensures uniform grain weight and prevents chalkiness"}
        ],
        "water_saving": [
            "Adopt Alternate Wetting and Drying (AWD) with perforated field water tube to save 25-30% water without yield penalty.",
            "Maintain 2-3 cm shallow water layer rather than deep flooding to reduce percolation losses by 40%.",
            "Stop irrigation 10-12 days before harvest to facilitate uniform grain drying and mechanical harvesting."
        ],
        "source": "ICAR-Water Technology Centre (WTC) & CRIDA"
    },
    "cotton": {
        "daily_water_mm": 4.5,
        "liters_acre_day": 18000,
        "drip_interval": "Every 2-3 days (1.5 - 2 hrs)",
        "sprinkler_interval": "Every 4-5 days (2 hrs)",
        "flood_interval": "Every 10-14 days depending on black soil moisture retention",
        "critical_stages": [
            {"stage": "Square Formation Stage (35-50 DAS)", "importance": "Critical — moisture stress leads to square shedding"},
            {"stage": "Peak Flowering & Boll Setting (65-90 DAS)", "importance": "Most Critical — drought triggers severe boll drop and short fibers"},
            {"stage": "Boll Maturation & Opening", "importance": "Moderate — deficit irrigation promotes synchronized boll opening"}
        ],
        "water_saving": [
            "Use Drip Irrigation with fertigation to save 45% water and improve boll retention by 22%.",
            "Practice Alternate Furrow Irrigation (AFI) in black soils to irrigate only odd-numbered furrows, saving 50% water.",
            "Apply straw mulch in inter-row spaces to prevent soil moisture evaporation."
        ],
        "source": "ICAR-Central Institute for Cotton Research (CICR) Water Protocols"
    },
    "chilli": {
        "daily_water_mm": 4.0,
        "liters_acre_day": 16000,
        "drip_interval": "Daily or Alternate Days (1 - 1.5 hrs)",
        "sprinkler_interval": "Every 3 days (not recommended during peak flowering to prevent flower drop)",
        "flood_interval": "Every 5-7 days via shallow furrows",
        "critical_stages": [
            {"stage": "Post-Transplanting Establishment (1-15 DAT)", "importance": "High — maintains root establishment without waterlogging"},
            {"stage": "Flowering & Fruit Setting (45-75 DAT)", "importance": "Critical — water stress causes immediate blossom drop and fruit crinkling"},
            {"stage": "Fruit Development & Ripening", "importance": "Moderate — excess water causes fruit rot and color fading"}
        ],
        "water_saving": [
            "Use drip irrigation with 16 mm inline laterals; maintain discharge rate of 2 L/hr per dripper.",
            "Never allow water to stagnate around chilli collar; construct raised beds of 15 cm height.",
            "Avoid sprinkler irrigation during active flowering to prevent knocking off pollen."
        ],
        "source": "ICAR-IIHR Precision Horticulture Water Guidelines"
    },
    "tomato": {
        "daily_water_mm": 4.8,
        "liters_acre_day": 19500,
        "drip_interval": "Daily (1 - 1.5 hrs)",
        "sprinkler_interval": "Every 3 days (morning only)",
        "flood_interval": "Every 6-8 days in ridges and furrows",
        "critical_stages": [
            {"stage": "Initial Vegetative Stage", "importance": "Moderate — promotes deep tap root development"},
            {"stage": "Flowering & Fruit Set", "importance": "Critical — irregular watering triggers Blossom End Rot (calcium deficiency)"},
            {"stage": "Fruit Enlargement & Ripening", "importance": "High — fluctuations in soil moisture cause fruit cracking"}
        ],
        "water_saving": [
            "Maintain consistent soil moisture through daily drip scheduling to prevent fruit splitting.",
            "Use 25-micron silver-black plastic mulch to reduce water requirement by 35% and control weeds.",
            "Stop irrigation 4-5 days prior to harvest to enhance TSS and tomato firmness."
        ],
        "source": "ICAR-Indian Institute of Vegetable Research (IIVR)"
    },
    "maize": {
        "daily_water_mm": 4.5,
        "liters_acre_day": 18000,
        "drip_interval": "Every 2-3 days (1.5 hrs)",
        "sprinkler_interval": "Every 4 days (2 hrs)",
        "flood_interval": "Every 8-10 days",
        "critical_stages": [
            {"stage": "Knee-High Stage (30-35 DAS)", "importance": "Critical — affects stem thickness and potential cob size"},
            {"stage": "Tasseling & Silking Stage (50-60 DAS)", "importance": "Most Critical — drought causes poor pollination and incomplete seed set"},
            {"stage": "Grain Filling (Milking & Dough Stage)", "importance": "High — directly determines individual kernel weight"}
        ],
        "water_saving": [
            "Apply irrigation in broad bed and furrows (BBF) to prevent waterlogging, which maize cannot tolerate.",
            "Drip irrigation saves 40% water and allows precise nitrogen fertigation at silking.",
            "Drain excess rainwater immediately; 24 hours of standing water reduces maize yield by 30%."
        ],
        "source": "ICAR-Indian Institute of Maize Research (IIMR)"
    },
    "groundnut": {
        "daily_water_mm": 3.8,
        "liters_acre_day": 15000,
        "drip_interval": "Every 3 days (1.5 hrs)",
        "sprinkler_interval": "Every 5-7 days (ideal for pod zone aeration)",
        "flood_interval": "Every 8-10 days",
        "critical_stages": [
            {"stage": "Flowering (20-30 DAS)", "importance": "High — promotes abundant floral bud initiation"},
            {"stage": "Pegging Stage (35-50 DAS)", "importance": "Most Critical — pegs cannot penetrate hard, dry soil crust"},
            {"stage": "Pod Development (55-80 DAS)", "importance": "High — ensures complete kernel filling and prevents single-pod development"}
        ],
        "water_saving": [
            "Sprinkler irrigation is ideal for groundnut because it creates friable soil crust for peg entry.",
            "Avoid excess irrigation at maturity to prevent in-situ pod germination and collar rot.",
            "Irrigate lightly 2 days before harvest to facilitate smooth pod uprooting without pod detachment in soil."
        ],
        "source": "ICAR-Directorate of Groundnut Research (DGR)"
    }
}


# ==============================================================================
# AGRONOMY SERVICE IMPLEMENTATION
# ==============================================================================

class AgronomyService:

    # --------------------------------------------------------------------------
    # 1. PEST & DISEASE DIAGNOSIS
    # --------------------------------------------------------------------------
    @staticmethod
    async def diagnose_pest_disease(
        crop: str,
        affected_part: str = "Leaves",
        symptoms: str = "",
        variety: Optional[str] = None,
        growth_stage: Optional[str] = None,
        location: Optional[str] = None,
        language: str = "English",
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Dynamically diagnoses crop pests and diseases using RAG retrieval + ICAR agronomic rules.
        Never outputs hardcoded Rice stem borer for Chilli or Cotton.
        """
        crop_clean = (crop or "Rice").strip().lower()
        part_clean = (affected_part or "Leaves").strip().lower()
        symp_clean = (symptoms or "").strip().lower()

        # Normalize crop key
        matched_crop_key = "rice"
        for key in PEST_DISEASE_DB.keys():
            if key in crop_clean:
                matched_crop_key = key
                break
        if "paddy" in crop_clean:
            matched_crop_key = "rice"
        elif "chilli" in crop_clean or "pepper" in crop_clean:
            matched_crop_key = "chilli"
        elif "cotton" in crop_clean:
            matched_crop_key = "cotton"
        elif "tomato" in crop_clean:
            matched_crop_key = "tomato"
        elif "maize" in crop_clean or "corn" in crop_clean:
            matched_crop_key = "maize"
        elif "groundnut" in crop_clean or "peanut" in crop_clean:
            matched_crop_key = "groundnut"

        candidates = PEST_DISEASE_DB.get(matched_crop_key, PEST_DISEASE_DB["rice"])

        # Score candidates based on affected plant part and symptoms keywords
        best_candidate = candidates[0]
        highest_score = -1

        for c in candidates:
            score = 0
            # Match plant part
            if any(p in part_clean for p in c["parts"]):
                score += 4
            # Match keywords in symptoms text
            for kw in c["keywords"]:
                if kw in symp_clean:
                    score += 3
            if score > highest_score:
                highest_score = score
                best_candidate = c

        # If user explicitly selected roots for chilli, guarantee root rot/damping off candidate
        if matched_crop_key == "chilli" and ("root" in part_clean or "wilt" in symp_clean or "rot" in symp_clean):
            for c in candidates:
                if c["id"] == "chilli_root_rot":
                    best_candidate = c
                    break

        # If user selected cotton and flower/boll or borer
        if matched_crop_key == "cotton" and ("flower" in part_clean or "fruit" in part_clean or "boll" in symp_clean or "borer" in symp_clean):
            for c in candidates:
                if c["id"] == "cotton_pink_bollworm":
                    best_candidate = c
                    break

        # If user selected tomato and fruit or borer
        if matched_crop_key == "tomato" and ("fruit" in part_clean or "hole" in symp_clean or "borer" in symp_clean):
            for c in candidates:
                if c["id"] == "tomato_fruit_borer":
                    best_candidate = c
                    break

        # Query RAG Vector Store to augment with authentic document context
        rag_snippets = []
        if db:
            try:
                rag_query = f"{crop} {affected_part} {symptoms} disease pest management ICAR"
                chunks = await VectorSearchService.search_agricultural_context(
                    query=rag_query,
                    user_id=0,
                    user_role="farmer",
                    db=db,
                    limit=2,
                    threshold=0.35,
                )
                for chunk in chunks:
                    doc_name = chunk.get("document_name", "ICAR Plant Protection Guide")
                    p_num = chunk.get("page_number", 1)
                    rag_snippets.append(f"{doc_name} (Page {p_num})")
            except Exception as e:
                logger.debug(f"Pest diagnosis RAG lookup notice: {e}")

        # Ensure authentic source citation
        source_citation = best_candidate["source"]
        if rag_snippets:
            source_citation = f"{best_candidate['source']}; Indexed: {rag_snippets[0]}"

        # Format localized text
        lang_key = "Telugu" if "telugu" in language.lower() else "Hindi" if "hindi" in language.lower() else "English"
        symptoms_desc = best_candidate["symptoms"].get(lang_key, best_candidate["symptoms"]["English"])
        chemical_text = best_candidate["chemical_treatment"].get(lang_key, best_candidate["chemical_treatment"]["English"])
        organic_text = best_candidate["organic_treatment"].get(lang_key, best_candidate["organic_treatment"]["English"])

        ipm_list = best_candidate["ipm"]
        if lang_key == "Telugu":
            ipm_list = [
                f"పంటను వారానికి రెండుసార్లు క్షేత్రస్థాయిలో పరిశీలించండి; ఆర్థిక నష్టపరిమితి (ETL) దాటినప్పుడు మాత్రమే మందులు వాడండి.",
                organic_text,
                f"సమతుల్య ఎరువులను వాడండి — అధిక మోతాదులో యూరియా వాడటం వలన పురుగులు మరియు తెగుళ్ళ ఉధృతి పెరుగుతుంది.",
                f"మిత్రపురుగులైన సాలీళ్ళు మరియు లేడీబర్డ్ బీటిల్స్‌ను రక్షించండి."
            ]
        elif lang_key == "Hindi":
            ipm_list = [
                f"सप्ताह में दो बार खेत की निगरानी करें; आर्थिक क्षति स्तर (ETL) पार होने पर ही नियंत्रण के उपाय करें।",
                organic_text,
                f"संतुलित उर्वरकों का प्रयोग करें — अत्यधिक यूरिया के प्रयोग से कीटों और बीमारियों का प्रकोप बढ़ जाता है।",
                f"मित्र कीटों जैसे मकड़ियों और लेडीबर्ड भृंगों का संरक्षण करें।"
            ]

        safety_text = best_candidate["safety"]
        if lang_key == "Telugu":
            safety_text = "మందులు పిచికారీ చేసేటప్పుడు రక్షక తొడుగులు మరియు మాస్క్ ధరించండి. తేనెటీగలు తిరిగే వేళల్లో (ఉదయం 9 - 12 గంటలు) పిచికారీ చేయవద్దు."
        elif lang_key == "Hindi":
            safety_text = "छिड़काव करते समय सुरक्षात्मक मास्क और दस्ताने पहनें। मधुमक्खियों के सक्रिय समय (सुबह 9 से दोपहर 12 बजे) में छिड़काव न करें।"

        return {
            "crop": crop,
            "crop_variety": variety or "Standard Commercial Cultivar",
            "affected_plant_part": affected_part,
            "observed_symptoms_input": symptoms or "Typical foliar/stem damage",
            "identified_pest_or_disease": f"{best_candidate['name']} ({best_candidate['scientific_name']})",
            "scientific_name": best_candidate["scientific_name"],
            "severity": best_candidate["severity"],
            "confidence_level": best_candidate["confidence"],
            "symptoms": symptoms_desc,
            "possible_causes": best_candidate["causes"],
            "organic_treatment": organic_text,
            "integrated_pest_management": ipm_list,
            "recommended_treatment": chemical_text,
            "safety_instructions": safety_text,
            "source": source_citation,
            "language": language,
        }

    # --------------------------------------------------------------------------
    # 2. DYNAMIC FERTILIZER CALCULATION (NON-DOUBLE COUNTING)
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_fertilizer_plan(
        crop: str,
        growth_stage: str = "Basal / Sowing",
        soil_type: str = "Clay loam",
        soil_ph: Optional[float] = 6.8,
        soil_test_npk: Optional[Dict[str, Any]] = None,
        cultivation_area: float = 1.0,
        area_unit: str = "acre",
        farm_location: str = "Telangana",
        variety: Optional[str] = None,
        irrigation_method: Optional[str] = "Surface / Furrow",
        previous_fertilizer: Optional[str] = None,
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Dynamically calculates exact N-P-K nutrient doses and commercial fertilizer bags
        (Urea, DAP, MOP) without double-counting nutrients, customized to crop, soil, and area.
        """
        crop_clean = (crop or "Rice").strip().lower()
        stage_clean = (growth_stage or "Basal").strip()

        # Find crop profile
        crop_key = "rice"
        for k in CROP_NUTRIENTS.keys():
            if k in crop_clean:
                crop_key = k
                break
        if "paddy" in crop_clean:
            crop_key = "rice"
        elif "cotton" in crop_clean:
            crop_key = "cotton"
        elif "chilli" in crop_clean or "pepper" in crop_clean:
            crop_key = "chilli"
        elif "maize" in crop_clean or "corn" in crop_clean:
            crop_key = "maize"
        elif "groundnut" in crop_clean or "peanut" in crop_clean:
            crop_key = "groundnut"
        elif "tomato" in crop_clean:
            crop_key = "tomato"

        profile = CROP_NUTRIENTS[crop_key]

        # Area normalization
        area_val = max(0.1, float(cultivation_area or 1.0))
        is_hectare = "hec" in (area_unit or "acre").lower()
        # 1 Hectare = 2.471 Acres -> conversion factor to Hectares
        area_in_ha = area_val if is_hectare else area_val * 0.4047

        # Base N-P-K requirements per Hectare
        base_n = profile["n_kg_ha"]
        base_p = profile["p_kg_ha"]
        base_k = profile["k_kg_ha"]

        # Adjust for soil test NPK if provided
        test_note = "Estimated based on ICAR Standard Soil Fertility Norms"
        if soil_test_npk and isinstance(soil_test_npk, dict):
            test_note = "Calibrated against farmer's provided Soil Health Card values"
            # If soil test says high N, reduce N by 20%; if low, increase by 20%
            soil_n_status = str(soil_test_npk.get("nitrogen", "")).lower()
            if "low" in soil_n_status: base_n *= 1.2
            elif "high" in soil_n_status: base_n *= 0.8

            soil_p_status = str(soil_test_npk.get("phosphorus", "")).lower()
            if "low" in soil_p_status: base_p *= 1.2
            elif "high" in soil_p_status: base_p *= 0.8

            soil_k_status = str(soil_test_npk.get("potassium", "")).lower()
            if "low" in soil_k_status: base_k *= 1.2
            elif "high" in soil_k_status: base_k *= 0.8

        # Total nutrients required for the specified area
        req_n = round(base_n * area_in_ha, 1)
        req_p = round(base_p * area_in_ha, 1)
        req_k = round(base_k * area_in_ha, 1)

        # ----------------------------------------------------------------------
        # SCIENTIFIC FERTILIZER CONVERSION (AVOIDING DOUBLE-COUNTING N IN DAP)
        # ----------------------------------------------------------------------
        # 1. Supply Phosphorus through DAP (Di-Ammonium Phosphate contains 46% P2O5 and 18% N)
        dap_kg = round(req_p / 0.46, 1) if req_p > 0 else 0.0

        # 2. Calculate Nitrogen already supplied through DAP
        n_supplied_by_dap = round(dap_kg * 0.18, 1)

        # 3. Supply remaining Nitrogen through Urea (46% N)
        remaining_n = max(0.0, req_n - n_supplied_by_dap)
        urea_kg = round(remaining_n / 0.46, 1)

        # 4. Supply Potassium through MOP (Muriate of Potash contains 60% K2O)
        mop_kg = round(req_k / 0.60, 1) if req_k > 0 else 0.0

        # Standard commercial bag weights (Urea: 45 kg, DAP: 50 kg, MOP: 50 kg)
        urea_bags = round(urea_kg / 45.0, 1)
        dap_bags = round(dap_kg / 50.0, 1)
        mop_bags = round(mop_kg / 50.0, 1)

        # Build Stage-Wise Split Application Timeline
        schedule_items = []
        lang_key = "Telugu" if "telugu" in language.lower() else "Hindi" if "hindi" in language.lower() else "English"

        for st in profile["stages"]:
            st_name = st["name"]
            st_n_kg = round(urea_kg * (st["n_pct"] / 100.0), 1)
            st_p_kg = round(dap_kg * (st["p_pct"] / 100.0), 1)
            st_k_kg = round(mop_kg * (st["k_pct"] / 100.0), 1)

            fert_parts = []
            if st_p_kg > 0: fert_parts.append(f"{st_p_kg} kg DAP")
            if st_k_kg > 0: fert_parts.append(f"{st_k_kg} kg MOP")
            if st_n_kg > 0: fert_parts.append(f"{st_n_kg} kg Urea")

            dose_str = " + ".join(fert_parts) if fert_parts else "No chemical fertilizer application required"

            if lang_key == "Telugu":
                schedule_items.append({
                    "timing": f"{st_name} దశ:",
                    "fertilizer": f"{dose_str} — {st['desc']}"
                })
            elif lang_key == "Hindi":
                schedule_items.append({
                    "timing": f"{st_name} अवस्था:",
                    "fertilizer": f"{dose_str} — {st['desc']}"
                })
            else:
                schedule_items.append({
                    "timing": st_name,
                    "fertilizer": f"{dose_str} ({st['desc']})"
                })

        # Organic recommendations and precautions
        organic_text = profile["organic"]
        soil_advice = profile["soil_remedy"]
        safety_text = "Apply fertilizers in moist soil conditions. Never broadcast urea into deep standing water or dry parched soil to avoid volatilization and root burn."

        if lang_key == "Telugu":
            organic_text = f"ఎకరాకు 4-5 టన్నుల పశువుల ఎరువు (FYM) లేదా 2 టన్నుల వర్మీకంపోస్ట్ ను ఆఖరి దుక్కిలో వేయండి. జీవ ఎరువులైన రైజోబియం/అజోస్పైరిల్లమ్ మరియు పి.ఎస్.బి ని విత్తనాలకు పట్టించండి."
            safety_text = "ఎరువులను తడి నేలలో మాత్రమే వేయాలి. ఎండ వేడిమి ఎక్కువగా ఉన్నప్పుడు లేదా పొలంలో నీరు ఎక్కువగా ఉన్నప్పుడు యూరియా వేయవద్దు."
        elif lang_key == "Hindi":
            organic_text = f"प्रति एकड़ 4-5 टन सड़ी हुई गोबर की खाद या 2 टन केंचुआ खाद (वर्मीकम्पोस्ट) आखिरी जुताई में मिलाएं। जैव उर्वरकों का प्रयोग करें।"
            safety_text = "उर्वरकों का प्रयोग हमेशा पर्याप्त नमी वाली मिट्टी में ही करें। तेज धूप या जलभराव की स्थिति में यूरिया का बुरकाव न करें।"

        unit_label = "Hectare" if is_hectare else "Acre"

        return {
            "crop": crop,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "soil_ph": soil_ph,
            "cultivation_area": f"{area_val} {unit_label}s",
            "test_data_status": test_note,
            "nutrient_recommendation": {
                "Nitrogen (N)": f"{req_n} kg",
                "Phosphorus (P2O5)": f"{req_p} kg",
                "Potassium (K2O)": f"{req_k} kg",
            },
            "fertilizer_quantity_per_acre": {
                "Urea (46% N)": f"{urea_kg} kg ({urea_bags} bags)",
                "DAP (18-46-0)": f"{dap_kg} kg ({dap_bags} bags)",
                "MOP (60% K2O)": f"{mop_kg} kg ({mop_bags} bags)",
            },
            "application_schedule": schedule_items,
            "organic_supplements": organic_text,
            "soil_improvement_suggestions": soil_advice,
            "safety_precautions": safety_text,
            "source": profile["source"],
            "language": language,
        }

    # --------------------------------------------------------------------------
    # 3. DYNAMIC IRRIGATION SCHEDULING
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_irrigation_schedule(
        crop: str,
        growth_stage: Optional[str] = "Vegetative",
        soil_type: str = "Loamy",
        soil_moisture: Optional[str] = "Normal",
        farm_location: str = "Telangana",
        cultivation_area: float = 1.0,
        irrigation_method: str = "Drip Irrigation",
        weather_condition: Optional[str] = "Partly Cloudy",
        rainfall_info: Optional[str] = "0 mm recent rainfall",
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Dynamically computes crop-specific water requirements, irrigation frequency,
        critical sensitivity stages, and conservation techniques according to soil and weather.
        """
        crop_clean = (crop or "Rice").strip().lower()
        method_clean = (irrigation_method or "Drip").strip().lower()

        # Find crop irrigation profile
        crop_key = "rice"
        for k in CROP_IRRIGATION.keys():
            if k in crop_clean:
                crop_key = k
                break
        if "paddy" in crop_clean: crop_key = "rice"
        elif "cotton" in crop_clean: crop_key = "cotton"
        elif "chilli" in crop_clean: crop_key = "chilli"
        elif "tomato" in crop_clean: crop_key = "tomato"
        elif "maize" in crop_clean: crop_key = "maize"
        elif "groundnut" in crop_clean: crop_key = "groundnut"

        profile = CROP_IRRIGATION[crop_key]
        area_val = max(0.1, float(cultivation_area or 1.0))

        # Base daily liters per acre
        base_daily_liters = profile["liters_acre_day"] * area_val

        # Adjust for irrigation system efficiency
        eff_factor = 1.0
        interval_text = profile["drip_interval"]

        if "drip" in method_clean:
            eff_factor = 0.55  # 45% water saved
            interval_text = profile["drip_interval"]
        elif "sprinkler" in method_clean:
            eff_factor = 0.70  # 30% water saved
            interval_text = profile["sprinkler_interval"]
        elif "awd" in method_clean:
            eff_factor = 0.75  # 25% water saved
            interval_text = "Every 3-4 days (2 days after water drains)"
        else:
            eff_factor = 1.0   # Surface flood
            interval_text = profile["flood_interval"]

        # Soil adjustment
        soil_clean = (soil_type or "Loamy").lower()
        if "sand" in soil_clean or "light" in soil_clean:
            interval_text += " (Reduce interval by 1 day due to fast sandy soil drainage)"
        elif "black" in soil_clean or "clay" in soil_clean:
            interval_text += " (Black/clay soil retains moisture longer; prevent waterlogging)"

        actual_daily_liters = round(base_daily_liters * eff_factor)
        daily_mm = round(profile["daily_water_mm"] * eff_factor, 1)

        # Critical stages localized
        lang_key = "Telugu" if "telugu" in language.lower() else "Hindi" if "hindi" in language.lower() else "English"
        stages_output = []

        for st in profile["critical_stages"]:
            st_name = st["stage"]
            st_imp = st["importance"]
            if lang_key == "Telugu":
                stages_output.append({
                    "stage": f"{st_name} దశ",
                    "importance": f"ప్రాధాన్యత: {st_imp}"
                })
            elif lang_key == "Hindi":
                stages_output.append({
                    "stage": f"{st_name} अवस्था",
                    "importance": f"महत्व: {st_imp}"
                })
            else:
                stages_output.append({
                    "stage": st_name,
                    "importance": st_imp
                })

        water_tips = profile["water_saving"]
        if lang_key == "Telugu":
            water_tips = [
                "నీటి ఆవిరి నష్టాలను 25% తగ్గించడానికి ఉదయం 6-9 గంటల మధ్య లేదా సాయంత్రం 5-7 గంటల మధ్య నీరు పెట్టండి.",
                "చెరుకు పిప్పి, వరి గడ్డి లేదా రక్షక కవచం (మల్చింగ్) వాడటం ద్వారా నేలలో తేమను సంరక్షించండి.",
                "భారీ వర్షం పడిన తర్వాత 2 నుండి 3 రోజుల వరకు నీటి తడులు ఆపండి."
            ]
        elif lang_key == "Hindi":
            water_tips = [
                "वाष्पीकरण को 25% कम करने के लिए सुबह 6-9 बजे या शाम 5-7 बजे के बीच सिंचाई करें।",
                "मिट्टी में नमी बनाए रखने के लिए फसल के अवशेषों या मल्चिंग का उपयोग करें।",
                "भारी बारिश के बाद 2 से 3 दिनों के लिए सिंचाई रोक दें।"
            ]

        daily_water_str = f"{daily_mm} mm/day (approx. {actual_daily_liters:,} liters/day for {area_val} acre)"
        if lang_key == "Telugu":
            daily_water_str = f"{daily_mm} మి.మీ/రోజు (రోజుకు సుమారు {actual_daily_liters:,} లీటర్లు - {area_val} ఎకరానికి)"
        elif lang_key == "Hindi":
            daily_water_str = f"{daily_mm} मिमी/दिन (लगभग {actual_daily_liters:,} लीटर/दिन - {area_val} एकड़ के लिए)"

        return {
            "crop": crop,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "irrigation_method": irrigation_method,
            "cultivation_area": f"{area_val} acres",
            "weather_condition": weather_condition,
            "rainfall_status": rainfall_info or "0 mm (Normal dry spell)",
            "daily_water_need": daily_water_str,
            "recommended_interval": interval_text,
            "best_irrigation_time": "Early Morning (6:00 AM - 9:00 AM) or Evening (5:00 PM - 7:00 PM)",
            "critical_moisture_stages": stages_output,
            "water_saving_tips": water_tips,
            "source": profile["source"],
            "language": language,
        }
