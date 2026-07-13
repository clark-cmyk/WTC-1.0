"""China Policy track schema and export format versions."""

TRACK_ID = "china_policy"
SCHEMA_VERSION = "1.0.0"
EXPORT_FORMAT = "CHINA POLICY EXPORT v1.0"

# Parquet filename stem (lives under data/china_policy/v1/)
PARQUET_FILENAME = "china_policy_observations.parquet"

# Global track uses data/global/ — never write China data there.
CHINA_DATA_ROOT = "data/china_policy"
GLOBAL_DATA_ROOT = "data/global"