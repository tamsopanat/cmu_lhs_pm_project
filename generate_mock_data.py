import csv
import random
import math
from datetime import datetime, timedelta

def generate_data():
    # Setup Location Hierarchy
    locations = {
        "Chiang Mai": {
            "Mueang Chiang Mai": ["Suthep", "Chang Phueak", "Sri Phum", "Pa Daet", "Mae Hia"],
            "Mae Rim": ["Mae Sa", "Rim Tai", "Pong Yaeng"],
            "Hang Dong": ["Hang Dong", "San Phak Wan", "Nam Phrae"],
            "San Sai": ["San Sai Luang", "San Pa Pao", "Nong Han"]
        },
        "Lampang": {
            "Mueang Lampang": ["Phra Bat", "Hua Wiang", "Phichai", "Chomphu", "Pong Saen Thong"],
            "Ko Kha": ["Ko Kha", "Sala", "Na Kaeo"],
            "Hang Chat": ["Hang Chat", "Pong Yang Khok"]
        }
    }
    
    start_date = datetime(2026, 4, 10, 0, 0, 0)
    num_days = 31 # Up to May 10, 2026
    num_hours = num_days * 24

    env_filename = "environmental.csv"
    env_headers = ["date", "province", "amphoe", "tambon", "pm25_avg", "temperature_avg"]
    
    with open(env_filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(env_headers)
        
        # Iterate through the hierarchy
        for prov, amphoes in locations.items():
            for amphoe, tambons in amphoes.items():
                for tambon in tambons:
                    # Simulate a trend: getting hotter and worse air quality towards May
                    base_pm25 = random.randint(30, 80)
                    
                    # Lampang is generally slightly hotter than Chiang Mai
                    temp_boost = 2.0 if prov == "Lampang" else 0.0
                    base_temp = random.uniform(30.0, 35.0) + temp_boost
                    
                    for h in range(num_hours):
                        current_date = start_date + timedelta(hours=h)
                        date_str = current_date.strftime("%Y-%m-%d %H:%M:%S")
                        
                        day_index = h / 24.0
                        hour_of_day = current_date.hour
                        
                        # Add diurnal variations (Temp peaks in afternoon, PM2.5 peaks in morning/night)
                        temp_diurnal = -5 * math.cos((hour_of_day - 4) * math.pi / 12)
                        pm25_diurnal = 10 * math.cos((hour_of_day - 2) * math.pi / 12)
                        
                        # Add noise and an upward trend
                        pm25 = int(base_pm25 + (day_index * 3.5) + pm25_diurnal + random.randint(-10, 15))
                        temp = round(base_temp + (day_index * 0.2) + temp_diurnal + random.uniform(-1.0, 1.0), 1)
                        
                        # Cap the values to realistic extremes
                        pm25 = max(15, min(pm25, 250))
                        temp = max(25.0, min(temp, 44.0))
                        
                        writer.writerow([date_str, prov, amphoe, tambon, pm25, temp])

    print(f"✅ Generated {env_filename} successfully.")

    pat_filename = "patients.csv"
    pat_headers = [
        "patient_id", "name_masked", "sex", "age", "province", "amphoe", "tambon", "last_contact_date",
        "age_over_65", "age_under_5", "pregnant", "bedridden_immobile", "outdoor_worker", 
        "copd", "asthma", "cardiovascular_disease", "diabetes", "ckd", "hypertension", "lung_cancer", "post_covid"
    ]
    
    thai_first_names = ["Somchai", "Mali", "Anong", "Kittipong", "Siriporn", "Nattapong", "Wipawan", "Surasak", "Pornthip", "Arunee"]
    thai_last_initials = ["P.", "S.", "W.", "K.", "T.", "N.", "J.", "M."]
    
    with open(pat_filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(pat_headers)
        
        # Generate 1500 mock patients to fill the expanded province/amphoe list
        for i in range(1, 1501):
            pid = f"CM-{random.randint(1000, 9999)}"
            name = f"{random.choice(thai_first_names)} {random.choice(thai_last_initials)}"
            sex = random.choice(["M", "F"])
            age = random.randint(2, 90)
            
            # Select random location from hierarchy
            prov = random.choice(list(locations.keys()))
            amphoe = random.choice(list(locations[prov].keys()))
            tambon = random.choice(locations[prov][amphoe])
            
            # Generate a recent contact date
            contact_days_ago = random.randint(1, 60)
            contact_date = (start_date + timedelta(days=num_days) - timedelta(days=contact_days_ago)).strftime("%Y-%m-%d")
            
            # Demographics booleans
            age_over_65 = age > 65
            age_under_5 = age < 5
            pregnant = sex == "F" and 18 <= age <= 40 and random.random() < 0.05
            bedridden_immobile = age_over_65 and random.random() < 0.2
            outdoor_worker = 18 <= age <= 60 and random.random() < 0.3
            
            # Health conditions booleans (weighted by age roughly)
            age_factor = age / 100
            copd = random.random() < (0.1 + age_factor * 0.3)
            asthma = random.random() < 0.15
            cvd = random.random() < (0.05 + age_factor * 0.4)
            diabetes = random.random() < (0.05 + age_factor * 0.3)
            ckd = random.random() < (0.02 + age_factor * 0.2)
            hypertension = random.random() < (0.1 + age_factor * 0.5)
            lung_cancer = random.random() < (0.01 + age_factor * 0.1)
            post_covid = random.random() < 0.2
            
            writer.writerow([
                pid, name, sex, age, "Chiang Mai", "Mueang Chiang Mai", tambon, contact_date,
                age_over_65, age_under_5, pregnant, bedridden_immobile, outdoor_worker,
                copd, asthma, cvd, diabetes, ckd, hypertension, lung_cancer, post_covid
            ])

    print(f"✅ Generated {pat_filename} successfully.")

if __name__ == "__main__":
    generate_data()