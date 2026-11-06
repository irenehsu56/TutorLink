import json
import os

import mysql.connector
from dotenv import load_dotenv

from pathlib import Path

# 專案路徑設定
# scripts/ 的上一層就是 TutorLink 根目錄
BASE_DIR = Path(__file__).resolve().parent.parent

# 讀取 TutorLink 根目錄的 .env
load_dotenv(BASE_DIR / ".env")

# 老師測試資料 JSON
JSON_PATH = BASE_DIR / "static" / "data" / "teachers.json"

# 讀取 JSON
with open(JSON_PATH, "r", encoding="utf-8") as file:
    teachers = json.load(file)

# 連線到 RDS MySQL
connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl_disabled=False,
)

cursor = connection.cursor()


try:
    sql = """
        INSERT INTO teachers (
            id, name, gender,
            subjects, grades, hourly_rate,
            education, experience, intro
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            gender = VALUES(gender),
            subjects = VALUES(subjects),
            grades = VALUES(grades),
            hourly_rate = VALUES(hourly_rate),
            education = VALUES(education),
            experience = VALUES(experience),
            intro = VALUES(intro)
    """

    # 新增教學地區，避免重複寫入相同地區
    location_sql = """
        INSERT INTO teacher_locations (
            teacher_id, city, district
        )
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            district = VALUES(district)
    """

    for teacher in teachers:

        # 老師基本資料
        values = (
            teacher["id"],
            teacher["name"],
            teacher.get("gender"),
            json.dumps(teacher["subjects"], ensure_ascii=False),
            json.dumps(teacher["grades"], ensure_ascii=False),
            teacher["hourlyRate"],
            teacher.get("education"),
            teacher.get("experience"),
            teacher.get("intro"),
        )

        # 寫入 teachers
        cursor.execute(sql, values)

        # 取得老師 ID 與教學地區
        teacher_id = teacher["id"]

        # 兼容目前 teachers.json 的單一地區格式
        locations = teacher.get("locations")

        if locations is None:
            locations = [{
                "city": teacher["city"],
                "district": teacher["district"]
            }]

        # 寫入 teacher_locations
        for location in locations:
            cursor.execute(
                location_sql,
                (
                    teacher_id,
                    location["city"],
                    location["district"]
                )
            )

    # 兩張資料表都寫入成功才提交
    connection.commit()

    print(f"成功處理 {len(teachers)} 筆老師資料！")

    # 確認老師資料總筆數
    cursor.execute("SELECT COUNT(*) FROM teachers")
    count = cursor.fetchone()[0]

    print(f"目前 teachers 資料表共有 {count} 筆資料。")

    # 確認教學地區資料總筆數
    cursor.execute("SELECT COUNT(*) FROM teacher_locations")
    location_count = cursor.fetchone()[0]

    print(f"目前 teacher_locations 資料表共有 {location_count} 筆資料。")

except Exception:
    connection.rollback()
    raise

finally:
    cursor.close()
    connection.close()
