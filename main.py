from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
import os
import uvicorn

app = FastAPI(title="CMU Learning Health System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_frontend():
    return FileResponse("main.html")

@app.get("/api/locations")
def get_locations():
    """
    Reads the environmental data and returns the exact location hierarchy
    present in the CSV file for dynamic dropdown population.
    """
    if not os.path.exists("environmental.csv"):
         return JSONResponse(
            status_code=404, 
            content={"error": "Data file missing. Please run generate_mock_data.py first."}
        )
    
    # Only read the location columns to save memory
    df = pd.read_csv("environmental.csv", usecols=["province", "amphoe", "tambon"])
    
    hierarchy = {}
    for prov in df['province'].dropna().unique():
        hierarchy[prov] = {}
        prov_df = df[df['province'] == prov]
        for amphoe in prov_df['amphoe'].dropna().unique():
            tambons = prov_df[prov_df['amphoe'] == amphoe]['tambon'].dropna().unique().tolist()
            hierarchy[prov][amphoe] = tambons
            
    return hierarchy

@app.get("/api/data")
def get_dashboard_data(
    province: str = "Chiang Mai", 
    amphoe: str = "All Amphoe", 
    tambon: str = "All Tambon", 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None,
    mode: str = "daily",
    chk_age_65: bool = True,
    chk_age_5: bool = False,
    chk_bedridden: bool = True,
    chk_worker: bool = False,
    chk_pregnant: bool = False,
    chk_copd: bool = True,
    chk_asthma: bool = True,
    chk_cvd: bool = False,
    chk_diabetes: bool = False,
    chk_ht: bool = False
):
    """
    Reads the CSV files, merges environmental and patient data,
    and returns calculated cohorts and charting data based on dates.
    """
    if not os.path.exists("environmental.csv") or not os.path.exists("patients.csv"):
        return JSONResponse(
            status_code=404, 
            content={"error": "Data files missing. Please run generate_mock_data.py first."}
        )

    # 1. Process Environmental Data
    env_df = pd.read_csv("environmental.csv")
    env_df['date'] = pd.to_datetime(env_df['date'])
    
    # Filter by hierarchy
    env_loc = env_df[env_df['province'] == province].copy()
    if amphoe != "All Amphoe":
        env_loc = env_loc[env_loc['amphoe'] == amphoe]
    if tambon != "All Tambon":
        env_loc = env_loc[env_loc['tambon'] == tambon]
    
    # Aggregate data to a single regional hourly timeline using mean values
    env_loc = env_loc.groupby('date').agg({
        'pm25_avg': 'mean',
        'temperature_avg': 'mean'
    }).reset_index()

    # Filter by selected date range
    if start_date and end_date:
        start_dt = pd.to_datetime(start_date)
        # Add 1 day minus 1 second to end_date to ensure we capture all 24 hours of the final day
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1, seconds=-1)
        env_loc = env_loc[(env_loc['date'] >= start_dt) & (env_loc['date'] <= end_dt)]
    
    delta_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days if start_date and end_date else 0
    
    if delta_days == 0:
        # If the range is exactly 1 day, show Hourly trend
        env_grouped = env_loc.copy()
        labels = [d.strftime('%H:00') for d in env_grouped['date']]
    elif mode == 'weekly' and delta_days >= 7:
        # Show Weekly trend if requested and range is long enough
        env_grouped = env_loc.groupby(pd.Grouper(key='date', freq='W')).agg({
            'pm25_avg': 'max',
            'temperature_avg': 'max'
        }).reset_index()
        labels = ["Wk of " + d for d in env_grouped['date'].dt.strftime('%b %d').tolist()]
    else:
        # Default to Daily Max trend
        env_grouped = env_loc.groupby(env_loc['date'].dt.date).agg({
            'pm25_avg': 'max',
            'temperature_avg': 'max'
        }).reset_index()
        labels = [d.strftime('%b %d') for d in env_grouped['date']]
        
    recent_env = env_grouped
    pm25_data = recent_env['pm25_avg'].tolist()
    temp_data = recent_env['temperature_avg'].tolist()
    
    # Determine current risk thresholds based on the most recent day (or max of period)
    max_pm25 = max(pm25_data) if pm25_data else 0
    max_temp = max(temp_data) if temp_data else 0
    
    air_hazard_active = max_pm25 >= 150
    temp_hazard_active = max_temp >= 38.0

    # 2. Process Patient Data and Calculate Vulnerability Cohorts
    pat_df = pd.read_csv("patients.csv")
    
    # Filter patients by hierarchy
    pat_loc = pat_df[pat_df['province'] == province].copy()
    if amphoe != "All Amphoe":
        pat_loc = pat_loc[pat_loc['amphoe'] == amphoe]
    if tambon != "All Tambon":
        pat_loc = pat_loc[pat_loc['tambon'] == tambon]
    
    air_risk_patients = []
    thermal_risk_patients = []
    combined_risk_patients = []

    admin_air_count = 0
    admin_thermal_count = 0
    admin_combined_count = 0

    for _, row in pat_loc.iterrows():
        # --- PROVIDER VIEW LOGIC (Filtered by Checkboxes) ---
        has_resp_issue = False
        if chk_copd and row['copd']: has_resp_issue = True
        if chk_asthma and row['asthma']: has_resp_issue = True
        
        has_thermal_issue = False
        if chk_age_65 and row['age_over_65']: has_thermal_issue = True
        if chk_age_5 and row['age_under_5']: has_thermal_issue = True
        if chk_bedridden and row['bedridden_immobile']: has_thermal_issue = True
        if chk_worker and row['outdoor_worker']: has_thermal_issue = True
        if chk_pregnant and row['pregnant']: has_thermal_issue = True
        if chk_cvd and row['cardiovascular_disease']: has_thermal_issue = True
        if chk_diabetes and row['diabetes']: has_thermal_issue = True
        if chk_ht and row['hypertension']: has_thermal_issue = True
        
        is_air_risk = air_hazard_active and has_resp_issue
        is_thermal_risk = temp_hazard_active and has_thermal_issue
        
        # --- ADMIN VIEW LOGIC (Unfiltered All Cases) ---
        admin_has_resp = row.get('copd', False) or row.get('asthma', False) or row.get('lung_cancer', False) or row.get('post_covid', False)
        admin_has_thermal = (
            row.get('age_over_65', False) or row.get('age_under_5', False) or row.get('bedridden_immobile', False) or 
            row.get('outdoor_worker', False) or row.get('pregnant', False) or row.get('cardiovascular_disease', False) or 
            row.get('diabetes', False) or row.get('hypertension', False) or row.get('ckd', False)
        )
        
        admin_air_risk = air_hazard_active and admin_has_resp
        admin_thermal_risk = temp_hazard_active and admin_has_thermal
        
        if admin_air_risk and admin_thermal_risk:
            admin_combined_count += 1
        elif admin_air_risk:
            admin_air_count += 1
        elif admin_thermal_risk:
            admin_thermal_count += 1

        # Build display flags for UI (shows what underlying conditions this patient actually has)
        flags = []
        if row['age'] > 65: flags.append(f"Age {row['age']}")
        elif row['age'] < 5: flags.append(f"Age {row['age']}")
        if row['bedridden_immobile']: flags.append("Bedridden")
        if row['pregnant']: flags.append("Pregnant")
        if row['outdoor_worker']: flags.append("Outdoor Worker")
        if row['copd']: flags.append("COPD")
        if row['asthma']: flags.append("Asthma")
        if row['cardiovascular_disease']: flags.append("CVD")
        if row['diabetes']: flags.append("Diabetes")
        if row['hypertension']: flags.append("Hypertension")
        
        flags_str = ", ".join(flags) if flags else "General Risk"

        patient_obj = {
            "name_masked": row['name_masked'],
            "patient_id": row['patient_id'],
            "tambon": row['tambon'],
            "flags": flags_str
        }

        # Categorize
        if is_air_risk and is_thermal_risk:
            patient_obj["risk_type"] = "COMBINED"
            patient_obj["env_details"] = f"PM2.5 ({int(max_pm25)}) + Heat ({max_temp}°C)"
            combined_risk_patients.append(patient_obj)
        elif is_air_risk:
            patient_obj["risk_type"] = "AIR"
            patient_obj["env_details"] = f"PM2.5 ({int(max_pm25)})"
            air_risk_patients.append(patient_obj)
        elif is_thermal_risk:
            patient_obj["risk_type"] = "THERMAL"
            patient_obj["env_details"] = f"Extreme Heat ({max_temp}°C)"
            thermal_risk_patients.append(patient_obj)

    # Combine for the table (sorted by severity)
    all_targeted = combined_risk_patients + thermal_risk_patients + air_risk_patients

    return {
        "environment": {
            "labels": labels,
            "pm25": [int(x) for x in pm25_data],
            "temperature": [round(x, 1) for x in temp_data]
        },
        "cohorts": {
            "air_risk_count": len(air_risk_patients),
            "thermal_risk_count": len(thermal_risk_patients),
            "combined_risk_count": len(combined_risk_patients),
            "total_risk_count": len(all_targeted)
        },
        "admin_cohorts": {
            "air_risk_count": admin_air_count,
            "thermal_risk_count": admin_thermal_count,
            "combined_risk_count": admin_combined_count
        },
        "patients": all_targeted[:15] # Return top 15 for dashboard display
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)