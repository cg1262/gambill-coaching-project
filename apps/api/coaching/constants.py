from __future__ import annotations

from typing import Any

COMMON_SKILLS = {
    "python", "sql", "dbt", "airflow", "spark", "pyspark", "databricks", "snowflake",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "power bi", "tableau",
    "kafka", "flink", "etl", "elt", "medallion", "lakehouse", "data modeling", "ci/cd",
}

COMMON_DOMAINS = {
    "finance", "healthcare", "retail", "manufacturing", "telecom", "insurance", "saas",
    "ecommerce", "logistics", "public sector", "energy", "education",
}

COMMON_TOOLS = {
    "databricks", "snowflake", "bigquery", "redshift", "postgres", "mysql", "airflow",
    "dbt", "power bi", "tableau", "git", "github", "gitlab", "jira", "confluence",
}

TAG_TOPIC_MAP = {
    "discovery": ["career", "communication", "architecture"],
    "bronze": ["pipeline", "data-engineering", "pyspark", "spark", "databricks", "big-data"],
    "silver": ["sql", "quality", "performance", "query-optimization"],
    "gold": ["bi", "visualization", "storytelling", "warehouse", "dimensional-modeling", "star-schema"],
    "roi": ["bi", "visualization", "communication"],
    "governance": ["governance", "data-management"],
    "architecture": ["architecture", "distributed-systems", "data-platform"],
}

REQUIRED_SECTION_FLOW = [
    "schema_version",
    "project_title",
    "candidate_profile",
    "business_outcome",
    "solution_architecture",
    "project_story",
    "milestones",
    "roi_dashboard_requirements",
    "resource_plan",
    "mentoring_cta",
    "project_charter",
]

CHARTER_REQUIRED_SECTION_FLOW = [
    "prerequisites_resources",
    "executive_summary",
    "technical_architecture",
    "implementation_plan",
    "deliverables_acceptance_criteria",
    "risks_assumptions",
    "stretch_goals",
]

RESUME_TOOL_KEYWORDS = [
    "python", "sql", "dbt", "airflow", "spark", "pyspark", "databricks", "snowflake", "bigquery", "redshift",
    "azure", "aws", "gcp", "power bi", "tableau", "looker", "kafka", "terraform", "docker", "kubernetes",
]

RESUME_DOMAIN_KEYWORDS = [
    "healthcare", "finance", "retail", "ecommerce", "logistics", "manufacturing", "insurance", "saas", "public sector", "education",
]

RESUME_PROJECT_KEYWORDS = [
    "medallion", "lakehouse", "etl", "elt", "cdc", "dashboard", "kpi", "data quality", "orchestration", "data modeling",
    "forecast", "a/b testing", "mlops", "batch", "streaming",
]

DATA_SOURCE_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "Sample Superstore Sales Dataset",
        "url": "https://www.kaggle.com/datasets/vivek468/superstore-dataset-final",
        "ingestion_doc_url": "https://www.kaggle.com/docs/api",
        "tags": {"retail", "ecommerce", "csv", "dashboard", "power bi", "sql"},
        "selection_rationale": "Provides order-level retail facts that are well suited for bronze-to-gold modeling, KPI design, and executive dashboard storytelling.",
    },
    {
        "name": "CoinGecko Simple Price API",
        "url": "https://api.coingecko.com/api/v3/simple/price",
        "ingestion_doc_url": "https://docs.coingecko.com/v3.0.1/reference/simple-price",
        "tags": {"finance", "crypto", "api", "python", "spark", "databricks", "realtime", "market"},
        "selection_rationale": "Supports near-real-time crypto market monitoring scenarios with fast price checks, timestamp handling, and latency-aware alerting use cases.",
    },
    {
        "name": "CoinGecko Markets API",
        "url": "https://api.coingecko.com/api/v3/coins/markets",
        "ingestion_doc_url": "https://docs.coingecko.com/v3.0.1/reference/coins-markets",
        "tags": {"finance", "crypto", "api", "json", "python", "spark", "databricks", "metadata"},
        "selection_rationale": "Provides richer market and coin metadata that works well for silver-layer flattening, rolling metrics, and alert logic in finance-style projects.",
    },
    {
        "name": "Open Charge Map API",
        "url": "https://openchargemap.org/site/develop/api",
        "ingestion_doc_url": "https://openchargemap.org/site/develop/api#/operations/get-poi",
        "tags": {"energy", "ev", "api", "json", "spark", "databricks"},
        "selection_rationale": "Gives public EV charging infrastructure and status data for resilient API ingestion, flattening, and operational analytics exercises.",
    },
    {
        "name": "OpenWeather One Call API",
        "url": "https://openweathermap.org/api/one-call-3",
        "ingestion_doc_url": "https://openweathermap.org/api/one-call-3#how",
        "tags": {"energy", "weather", "api", "time-series", "python"},
        "selection_rationale": "Adds external weather signals that support risk scoring, regional joins, and business-impact narratives for outage or utilization scenarios.",
    },
    {
        "name": "NYC TLC Trip Record Data",
        "url": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
        "ingestion_doc_url": "https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf",
        "tags": {"transport", "analytics", "sql", "power bi"},
        "selection_rationale": "Public trip-level facts are excellent for building medallion pipelines and KPI reporting exercises.",
    },
    {
        "name": "Bureau of Labor Statistics Public Data API",
        "url": "https://www.bls.gov/data/",
        "ingestion_doc_url": "https://www.bls.gov/developers/home.htm",
        "tags": {"economics", "api", "python", "time-series"},
        "selection_rationale": "Provides real API ingestion practice plus documented schemas for incremental loads and trend dashboards.",
    },
    {
        "name": "NYC Open Data (Socrata)",
        "url": "https://opendata.cityofnewyork.us/",
        "ingestion_doc_url": "https://dev.socrata.com/docs/",
        "tags": {"api", "etl", "governance", "data quality"},
        "selection_rationale": "Offers diverse public datasets with API docs suited for data quality checks and stakeholder-facing reporting.",
    },
    {
        "name": "Chicago Data Portal",
        "url": "https://data.cityofchicago.org/",
        "ingestion_doc_url": "https://dev.socrata.com/foundry/data.cityofchicago.org",
        "tags": {"city", "public", "dashboard", "bi"},
        "selection_rationale": "Good source for reproducible city analytics projects with clear ingestion endpoints and metadata.",
    },
]


STYLE_ANCHORS = {
    "globalmart": {
        "name": "GlobalMart Retail Intelligence Pipeline",
        "tone_cues": ["executive-ready", "decision-grade", "delivery accountability"],
        "required_signals": ["current_state", "future_state", "quantified KPI targets", "milestone acceptance checks"],
    },
    "voltstream": {
        "name": "VoltStream EV Grid Resilience",
        "tone_cues": ["systems thinking", "risk-aware", "operationally realistic"],
        "required_signals": ["realistic fictitious business narrative", "public datasource URLs", "explicit ingestion instructions"],
    },
    "ggn_market_monitor": {
        "name": "Global Giving Network Market & Donation Velocity Monitor",
        "tone_cues": ["real-time", "alert-driven", "financially precise"],
        "required_signals": ["API-first ingestion", "latency monitoring", "threshold-based business alerts"],
    },
}