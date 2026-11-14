"""Constants for the lunar landing site navigator."""

GRID_SPACING_M = 1000
GRID_LATITUDE_LIMIT_DEG = -85
HEIGHTS_M = (1, 5, 10)
HORIZON_AZIMUTH_COUNT = 720
REFINED_HORIZON_AZIMUTH_COUNT = 720
HORIZON_MAX_DISTANCE_M = 100_000
HORIZON_COMPARISON_DISTANCE_M = 50_000
HORIZON_COMPARISON_SAMPLE_COUNT = 100
EARTH_DELTA_DEG = 0.25
SUNLIGHT_BY_POWER = {"LOW": 30, "NORMAL": 50, "HIGH": 80}
GEOLOGY_RADIUS_M = 20_000
GEOLOGY_CLIP_LAT_DEG = -80
LARGE_CRATER_DIAMETER_KM = 20
REFERENCE_PERCENTILE = 95
ANALYSIS_CACHE_SIZE = 50
DEFAULT_ANALYSIS_TARGET_SECONDS = 10
SEPARATION_COEFFICIENT = 0.5
MARGINAL_LIMIT_RATIO = 0.9
REFINED_MIN_SPACING_M = 200
REFINED_TARGET_POINTS = 5000
MAX_CANDIDATES = 50
CORS_ORIGINS = ("*",)
SCORE_TAGS = (
    "Good Earth visibility", "Flat terrain", "Low roughness", "High sunlight",
    "Objective match",
)
LUNAR_RADIUS_M = 1_737_400

OBJECTIVES = (
    ("GENERAL", "General", False),
    ("POLAR_VOLATILES", "Understanding the character and origin of lunar polar volatiles", True),
    ("PLANETARY_PROCESSES", "Understanding planetary processes", True),
    ("IMPACT_HISTORY", "Interpreting the impact history of the Earth-Moon system", True),
    ("ANCIENT_SUN", "Revealing the record of the ancient sun and our astronomical environment", False),
    ("UNIQUE_OBSERVATION", "Observing the universe and the local space environment from a unique location", False),
    ("EXPERIMENTAL_SCIENCE", "Conducting experimental science in the lunar environment", False),
    ("EXPLORATION_RISKS", "Investigating and mitigating exploration risks", False),
)
COMMUNICATION_IMPORTANCE = {"INDEPENDENT": 1, "NORMAL": 3, "CRITICAL": 5}
MISSION_IMPORTANCE = {"CREWED": 5, "UNCREWED": 3}
POWER_IMPORTANCE = {"LOW": 1, "NORMAL": 3, "HIGH": 5}
OTHER_IMPORTANCE = 3
BASELINE_SYSTEMATIC_BIAS_THRESHOLD = 0.1
BASELINE_SAMPLE_COUNT = 2000
CALIBRATION_LOCAL_RADIUS_M = 2000
CALIBRATION_SAMPLES_PER_SITE = 25
CALIBRATION_HEIGHT_M = 1
CALIBRATION_RANDOM_SEED = 2027
