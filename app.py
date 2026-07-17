from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import numpy as np


app = FastAPI(title="CMU Learning Health System API")


# -----------------------------------
# CORS
# -----------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------
# Paths
# -----------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR2 = BASE_DIR / "data2"
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR.parent / "data"

DEMO_CSV = DATA_DIR / "demo_pm25_health_2000_rows.csv"
PATIENTS_CSV = DATA_DIR2 / "patients.csv"
PATIENT_VULNERABILITY_CSV = DATA_DIR / "patient_vulnerability.csv"
ENV_DAILY_CSV = DATA_DIR2 / "environment_daily.csv"
ENV_HOURLY_CSV = DATA_DIR2 / "environment_hourly.csv"
PATIENT_RISK_DAILY_CSV = DATA_DIR / "patient_risk_daily.csv"
AREA_ALERT_DAILY_CSV = DATA_DIR2 / "area_alert_daily.csv"
CONTACT_LOG_CSV = DATA_DIR / "contact_log.csv"


# -----------------------------------
# Helpers
# -----------------------------------
def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[WARN] CSV not found: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path)

    # Normalize location text so cascading filters do not leak values from other areas
    # because of hidden spaces or mixed text formats.
    for col in ["province", "amphoe", "tambon"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None"]), col] = None

    df = df.replace({np.nan: None})
    return df


def clean_records(df: pd.DataFrame):
    if df.empty:
        return []

    cleaned = df.replace({np.nan: None})
    return cleaned.to_dict(orient="records")


def to_bool_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )


def apply_exact_filter(df: pd.DataFrame, column: str, value: Optional[str]) -> pd.DataFrame:
    if value is None or value == "" or value == "all":
        return df

    if column not in df.columns:
        return df

    return df[df[column].astype(str) == str(value)]


def apply_date_filter(
    df: pd.DataFrame,
    date_col: str = "date",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Filter dates safely even when CSV stores M/D/YYYY or YYYY-MM-DD."""
    if df.empty or date_col not in df.columns:
        return df

    filtered = df.copy()
    date_series = pd.to_datetime(filtered[date_col], errors="coerce")

    if start_date:
        start_ts = pd.to_datetime(start_date, errors="coerce")
        if not pd.isna(start_ts):
            filtered = filtered[date_series >= start_ts]
            date_series = date_series.loc[filtered.index]

    if end_date:
        end_ts = pd.to_datetime(end_date, errors="coerce")
        if not pd.isna(end_ts):
            filtered = filtered[date_series <= end_ts]

    filtered[date_col] = pd.to_datetime(filtered[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    return filtered


def apply_bool_filter(df: pd.DataFrame, column: str, value: Optional[bool]) -> pd.DataFrame:
    if value is None:
        return df

    if column not in df.columns:
        return df

    return df[to_bool_series(df[column]) == value]


def first_available_df(*dfs: pd.DataFrame) -> pd.DataFrame:
    for item in dfs:
        if not item.empty:
            return item
    return pd.DataFrame()


# -----------------------------------
# Load CSV files
# -----------------------------------
demo_df = read_csv_safe(DEMO_CSV)
patients_df = read_csv_safe(PATIENTS_CSV)
vulnerability_df = read_csv_safe(PATIENT_VULNERABILITY_CSV)
env_daily_df = read_csv_safe(ENV_DAILY_CSV)
env_hourly_df = read_csv_safe(ENV_HOURLY_CSV)
patient_risk_daily_df = read_csv_safe(PATIENT_RISK_DAILY_CSV)
area_alert_daily_df = read_csv_safe(AREA_ALERT_DAILY_CSV)
contact_log_df = read_csv_safe(CONTACT_LOG_CSV)


def build_patient_master() -> pd.DataFrame:
    """
    รวม patients.csv + patient_vulnerability.csv + ข้อมูล risk ล่าสุด
    ถ้าไฟล์ใหม่ไม่มี จะ fallback ไปใช้ demo_pm25_health_2000_rows.csv
    """
    if patients_df.empty:
        return demo_df.copy()

    merged = patients_df.copy()

    if not vulnerability_df.empty and "patient_id" in merged.columns and "patient_id" in vulnerability_df.columns:
        merged = merged.merge(
            vulnerability_df,
            on="patient_id",
            how="left",
            suffixes=("", "_vuln"),
        )

    if (
        not patient_risk_daily_df.empty
        and "patient_id" in merged.columns
        and "patient_id" in patient_risk_daily_df.columns
    ):
        risk_latest = patient_risk_daily_df.copy()

        if "date" in risk_latest.columns:
            risk_latest["_date_sort"] = pd.to_datetime(risk_latest["date"], errors="coerce")
            risk_latest = risk_latest.sort_values("_date_sort")

        risk_latest = risk_latest.drop_duplicates("patient_id", keep="last")

        keep_cols = [
            col for col in [
                "patient_id",
                "date",
                "risk_score",
                "clinical_risk_score",
                "environmental_risk_score",
                "final_risk_level",
                "recommended_intervention",
                "province",
                "amphoe",
                "tambon",
            ]
            if col in risk_latest.columns
        ]

        risk_latest = risk_latest[keep_cols]

        merged = merged.merge(
            risk_latest,
            on="patient_id",
            how="left",
            suffixes=("", "_risk"),
        )

    return merged.replace({np.nan: None})


patient_master_df = build_patient_master()


# -----------------------------------
# Root
# -----------------------------------
@app.get("/")
def root():
    return {
        "message": "CMU Learning Health System API",
        "status": "running",
        "data_dir": str(DATA_DIR),
        "files": {
            "demo_rows": int(len(demo_df)),
            "patients_rows": int(len(patients_df)),
            "patient_vulnerability_rows": int(len(vulnerability_df)),
            "environment_daily_rows": int(len(env_daily_df)),
            "environment_hourly_rows": int(len(env_hourly_df)),
            "patient_risk_daily_rows": int(len(patient_risk_daily_df)),
            "area_alert_daily_rows": int(len(area_alert_daily_df)),
            "contact_log_rows": int(len(contact_log_df)),
        },
    }




@app.get("/ui")
def ui():
    index_path = BASE_DIR / "Index.html"
    if not index_path.exists():
        return {"error": "Index.html not found", "path": str(index_path)}
    return FileResponse(index_path)


@app.get("/debug/filter-test")
def debug_filter_test():
    both = patient_master_df.copy()
    both = apply_bool_filter(both, "age_over_65", True)
    both = apply_bool_filter(both, "age_under_5", True)
    over65 = apply_bool_filter(patient_master_df.copy(), "age_over_65", True)
    under5 = apply_bool_filter(patient_master_df.copy(), "age_under_5", True)
    return {
        "version": "v6-strict-filter-2026-05-19",
        "age_over_65_count": int(len(over65)),
        "age_under_5_count": int(len(under5)),
        "both_age_over_65_and_under_5_count": int(len(both)),
        "both_should_be_zero": True,
    }


# -----------------------------------
# Dashboard Summary
# -----------------------------------
@app.get("/dashboard/summary")
def dashboard_summary():
    base = first_available_df(patient_master_df, demo_df)

    total_patients = len(base)

    critical_count = 0
    high_count = 0
    avg_pm25 = None
    top_province = None

    if "final_risk_level" in base.columns:
        critical_count = len(base[base["final_risk_level"] == "CRITICAL"])
        high_count = len(base[base["final_risk_level"] == "HIGH"])

    pm_source = first_available_df(env_daily_df, demo_df)

    if not pm_source.empty and "pm25_avg" in pm_source.columns:
        avg_pm25 = round(pd.to_numeric(pm_source["pm25_avg"], errors="coerce").mean(), 2)

    if not pm_source.empty and "province" in pm_source.columns and "pm25_avg" in pm_source.columns:
        top_province = (
            pm_source.assign(pm25_avg_num=pd.to_numeric(pm_source["pm25_avg"], errors="coerce"))
            .groupby("province")["pm25_avg_num"]
            .mean()
            .sort_values(ascending=False)
            .index[0]
        )

    return {
        "total_patients": int(total_patients),
        "critical_risk_count": int(critical_count),
        "high_risk_count": int(high_count),
        "average_pm25": None if pd.isna(avg_pm25) else float(avg_pm25),
        "highest_pm25_province": top_province,
    }


# -----------------------------------
# Patients
# -----------------------------------
@app.get("/patients")
def get_patients(
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    risk: Optional[str] = None,
    age_over_65: Optional[bool] = Query(default=None),
    age_under_5: Optional[bool] = Query(default=None),
    pregnant: Optional[bool] = Query(default=None),
    bedridden_immobile: Optional[bool] = Query(default=None),
    outdoor_worker: Optional[bool] = Query(default=None),
    copd: Optional[bool] = Query(default=None),
    asthma: Optional[bool] = Query(default=None),
    cardiovascular_disease: Optional[bool] = Query(default=None),
    diabetes: Optional[bool] = Query(default=None),
    ckd: Optional[bool] = Query(default=None),
    hypertension: Optional[bool] = Query(default=None),
    lung_cancer: Optional[bool] = Query(default=None),
    post_covid: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=5000),
):
    filtered = patient_master_df.copy()

    filtered = apply_exact_filter(filtered, "province", province)
    filtered = apply_exact_filter(filtered, "amphoe", amphoe)
    filtered = apply_exact_filter(filtered, "tambon", tambon)
    filtered = apply_exact_filter(filtered, "final_risk_level", risk)

    bool_filters = {
        "age_over_65": age_over_65,
        "age_under_5": age_under_5,
        "pregnant": pregnant,
        "bedridden_immobile": bedridden_immobile,
        "outdoor_worker": outdoor_worker,
        "copd": copd,
        "asthma": asthma,
        "cardiovascular_disease": cardiovascular_disease,
        "diabetes": diabetes,
        "ckd": ckd,
        "hypertension": hypertension,
        "lung_cancer": lung_cancer,
        "post_covid": post_covid,
    }

    for column, value in bool_filters.items():
        filtered = apply_bool_filter(filtered, column, value)

    filtered = filtered.head(limit)
    return clean_records(filtered)


@app.get("/patients/{patient_id}")
def get_patient_detail(patient_id: str):
    if patient_master_df.empty or "patient_id" not in patient_master_df.columns:
        return {"error": "patient data not available"}

    patient = patient_master_df[patient_master_df["patient_id"].astype(str) == str(patient_id)]

    if patient.empty:
        return {"error": "patient not found"}

    return clean_records(patient.head(1))[0]


# -----------------------------------
# PM2.5 Trend
# -----------------------------------
@app.get("/trend/pm25")
def pm25_trend(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    mode: str = Query(default="daily", pattern="^(daily|hourly)$"),
):
    source = env_hourly_df.copy() if mode == "hourly" and not env_hourly_df.empty else env_daily_df.copy()

    if source.empty:
        source = demo_df.copy()

    source = apply_exact_filter(source, "province", province)
    source = apply_exact_filter(source, "amphoe", amphoe)
    source = apply_exact_filter(source, "tambon", tambon)
    source = apply_date_filter(source, "date", start_date, end_date)

    if source.empty:
        return []

    group_cols = ["date"]

    if mode == "hourly" and "hour" in source.columns:
        group_cols = ["date", "hour"]

    agg_dict = {}

    if "pm25_avg" in source.columns:
        agg_dict["pm25_avg"] = "mean"

    if "temperature_avg" in source.columns:
        agg_dict["temperature_avg"] = "mean"

    if "pm25_max" in source.columns:
        agg_dict["pm25_max"] = "max"

    if "temperature_max" in source.columns:
        agg_dict["temperature_max"] = "max"

    if not agg_dict:
        return clean_records(source.head(500))

    trend = (
        source.groupby(group_cols)
        .agg(agg_dict)
        .reset_index()
        .sort_values(group_cols)
    )

    for col in ["pm25_avg", "temperature_avg", "pm25_max", "temperature_max"]:
        if col in trend.columns:
            trend[col] = pd.to_numeric(trend[col], errors="coerce").round(2)

    return clean_records(trend)


# -----------------------------------
# Environment Endpoints
# -----------------------------------
@app.get("/environment/daily")
def environment_daily(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=10000),
):
    filtered = env_daily_df.copy()
    filtered = apply_exact_filter(filtered, "province", province)
    filtered = apply_exact_filter(filtered, "amphoe", amphoe)
    filtered = apply_exact_filter(filtered, "tambon", tambon)
    filtered = apply_date_filter(filtered, "date", start_date, end_date)
    return clean_records(filtered.head(limit))


@app.get("/environment/hourly")
def environment_hourly(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=20000),
):
    filtered = env_hourly_df.copy()
    filtered = apply_exact_filter(filtered, "province", province)
    filtered = apply_exact_filter(filtered, "amphoe", amphoe)
    filtered = apply_exact_filter(filtered, "tambon", tambon)
    filtered = apply_date_filter(filtered, "date", start_date, end_date)
    return clean_records(filtered.head(limit))


# -----------------------------------
# Area Alerts
# -----------------------------------
@app.get("/area-alerts/daily")
def area_alerts_daily(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=10000),
):
    filtered = area_alert_daily_df.copy()
    filtered = apply_exact_filter(filtered, "province", province)
    filtered = apply_exact_filter(filtered, "amphoe", amphoe)
    filtered = apply_exact_filter(filtered, "tambon", tambon)
    filtered = apply_date_filter(filtered, "date", start_date, end_date)
    return clean_records(filtered.head(limit))


# -----------------------------------
# Patient Risk Daily
# -----------------------------------
@app.get("/patient-risk/daily")
def patient_risk_daily(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    patient_id: Optional[str] = None,
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
    tambon: Optional[str] = None,
    risk: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=20000),
):
    filtered = patient_risk_daily_df.copy()

    filtered = apply_exact_filter(filtered, "patient_id", patient_id)
    filtered = apply_exact_filter(filtered, "province", province)
    filtered = apply_exact_filter(filtered, "amphoe", amphoe)
    filtered = apply_exact_filter(filtered, "tambon", tambon)
    filtered = apply_exact_filter(filtered, "final_risk_level", risk)
    filtered = apply_date_filter(filtered, "date", start_date, end_date)

    return clean_records(filtered.head(limit))


# -----------------------------------
# Contact Log
# -----------------------------------
@app.get("/contact-log")
def contact_log(
    patient_id: Optional[str] = None,
    contact_method: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=5000),
):
    filtered = contact_log_df.copy()

    filtered = apply_exact_filter(filtered, "patient_id", patient_id)
    filtered = apply_exact_filter(filtered, "contact_method", contact_method)
    filtered = apply_exact_filter(filtered, "status", status)

    return clean_records(filtered.head(limit))


# -----------------------------------
# Risk by Province
# -----------------------------------
@app.get("/risk/province")
def risk_by_province():
    source = first_available_df(patient_master_df, demo_df)

    if source.empty or "province" not in source.columns:
        return []

    agg_dict = {}

    if "patient_id" in source.columns:
        agg_dict["patient_id"] = "count"

    if "pm25_avg" in source.columns:
        agg_dict["pm25_avg"] = "mean"

    if not agg_dict:
        return []

    risk = source.groupby("province").agg(agg_dict).reset_index()

    rename_map = {
        "patient_id": "patient_count",
        "pm25_avg": "average_pm25",
    }

    risk = risk.rename(columns=rename_map)

    if "average_pm25" in risk.columns:
        risk["average_pm25"] = pd.to_numeric(risk["average_pm25"], errors="coerce").round(2)

    return clean_records(risk)


# -----------------------------------
# Available areas
# -----------------------------------
@app.get("/provinces")
def get_provinces():
    source = first_available_df(patient_master_df, env_daily_df, demo_df)

    if source.empty or "province" not in source.columns:
        return {"provinces": []}

    provinces = sorted(source["province"].dropna().astype(str).unique().tolist())
    return {"provinces": provinces}


@app.get("/amphoes")
def get_amphoes(province: Optional[str] = None):
    source = first_available_df(patient_master_df, env_daily_df, demo_df)

    source = apply_exact_filter(source, "province", province)

    if source.empty or "amphoe" not in source.columns:
        return {"amphoes": []}

    amphoes = sorted(source["amphoe"].dropna().astype(str).unique().tolist())
    return {"amphoes": amphoes}


@app.get("/tambons")
def get_tambons(
    province: Optional[str] = None,
    amphoe: Optional[str] = None,
):
    source = first_available_df(patient_master_df, env_daily_df, demo_df)

    source = apply_exact_filter(source, "province", province)
    source = apply_exact_filter(source, "amphoe", amphoe)

    if source.empty or "tambon" not in source.columns:
        return {"tambons": []}

    tambons = sorted(source["tambon"].dropna().astype(str).unique().tolist())
    return {"tambons": tambons}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
