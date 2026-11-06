# ==============================
# 匯入需要的套件
import json
import os
import mysql.connector
from decimal import Decimal
from typing import Literal

# 處理 JWT Token 的到期時間
from datetime import datetime, timedelta, timezone, date, time
# 處理台灣時區，用於判斷家教預約的取消期限
from zoneinfo import ZoneInfo
# JWT：產生及驗證登入憑證
import jwt
# 讀取 .env 環境變數
from dotenv import load_dotenv
# FastAPI：建立 API、處理錯誤及依賴注入
from fastapi import FastAPI, HTTPException, status, Depends, Request, UploadFile, File
# 從 HTTP Authorization Header 取得 Bearer Token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# 回傳 HTML 檔案
from fastapi.responses import FileResponse
# 使用 Jinja2 模板渲染 HTML，支援共用元件
from fastapi.templating import Jinja2Templates
# 提供 CSS、JavaScript、圖片等靜態檔案
from fastapi.staticfiles import StaticFiles
# Pydantic：驗證使用者傳入的資料格式
from pydantic import BaseModel, EmailStr, Field
# 密碼雜湊與驗證（目前使用 Argon2）
from pwdlib import PasswordHash

# 從 app/s3.py 匯入 AWS S3 相關功能
# upload_teacher_photo：上傳老師頭貼至 S3
# get_teacher_photo_url：產生私人頭貼的暫時讀取網址
from app.s3 import ( upload_teacher_photo, get_teacher_photo_url, delete_teacher_photo )
import logging

# AWS boto3 / botocore 的例外處理
# BotoCoreError：處理 AWS SDK 底層錯誤，例如連線或請求處理異常
# ClientError：處理 AWS 服務回傳的錯誤，例如 AccessDenied（權限不足）
from botocore.exceptions import BotoCoreError, ClientError

# ==============================
# 載入環境變數

# 讀取 .env 檔案中的設定
# 包含 MySQL 連線資訊及 JWT 密鑰
load_dotenv()

# JWT 簽署密鑰
# 用來防止 Token 被任意偽造
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]

# JWT 使用的簽署演算法，預設為 HS256
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# JWT 有效期限，單位為分鐘，預設 60 分鐘
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# ==============================
# 建立 FastAPI 應用程式

# 建立 FastAPI 物件
# title 會顯示在 Swagger UI (/docs)
app = FastAPI(title="TutorLink API")

# 設定靜態檔案資料夾
# 例如 /static/css/index.css
# 對應專案中的 static/css/index.css
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設定 Jinja2 HTML 模板資料夾
# 所有 HTML 統一存放於 templates/
# 共用元件則放在 templates/components/
templates = Jinja2Templates(directory="templates")

# ==============================
# 前端 HTML 頁面路由

# GET /
# 使用者進入網站首頁時，透過 Jinja2 模板渲染 index.html
@app.get("/", tags=["01｜網站頁面 Pages"])
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

# GET /teachers.html
# 使用者進入老師列表頁時，透過 Jinja2 模板渲染 teachers.html
@app.get("/teachers.html", tags=["01｜網站頁面 Pages"])
def teachers_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="teachers.html"
    )

# GET /teacher-detail.html
# 使用者進入老師詳細介紹頁面時，透過 Jinja2 模板渲染 teacher-detail.html
@app.get("/teacher-detail.html", tags=["01｜網站頁面 Pages"])
def teacher_detail_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="teacher-detail.html"
    )

# GET /become-teacher.html
# 使用者進入成為家教老師頁面時，透過 Jinja2 模板渲染 become-teacher.html
@app.get("/become-teacher.html", tags=["01｜網站頁面 Pages"])
def become_teacher_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="become-teacher.html"
    )

# GET /my-teacher-profile.html
# 老師進入自己的個人資料頁面時，透過 Jinja2 模板渲染 my-teacher-profile.html
@app.get("/my-teacher-profile.html", tags=["01｜網站頁面 Pages"])
def my_teacher_profile_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="my-teacher-profile.html"
    )

# GET /my-favorites.html
# 使用者進入我的收藏老師頁面時，透過 Jinja2 模板渲染 my-favorites.html
@app.get("/my-favorites.html", tags=["01｜網站頁面 Pages"])
def my_favorites_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="my-favorites.html"
    )

# GET /messages.html
# 使用者進入我的訊息頁面時，透過 Jinja2 模板渲染 messages.html
@app.get("/messages.html", tags=["01｜網站頁面 Pages"])
def messages_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="messages.html"
    )

# GET /calendar.html
# 使用者進入個人行事曆頁面時，透過 Jinja2 模板渲染 calendar.html
@app.get("/calendar.html", tags=["01｜網站頁面 Pages"])
def calendar_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="calendar.html"
    )

# ==============================
# 密碼與 JWT 驗證工具

# 建立密碼雜湊工具
# 註冊時：將明文密碼轉換成雜湊值
# 登入時：驗證輸入密碼是否符合資料庫中的雜湊值
password_hash = PasswordHash.recommended()

# 建立 Bearer Token 驗證工具
# 用於讀取 HTTP Header：
# Authorization: Bearer <token>
bearer_scheme = HTTPBearer()

# ==============================
# Pydantic 資料驗證模型

# 會員註冊時需要提供的資料
class UserRegister(BaseModel):
    # 姓名：至少 1 個字元，最多 50 個字元
    name: str = Field(min_length=1, max_length=50)

    # EmailStr 會檢查 Email 格式是否正確
    email: EmailStr

    # 密碼：至少 8 個字元，最多 128 個字元
    password: str = Field(min_length=8, max_length=128)

# 會員登入時需要提供的資料
class UserLogin(BaseModel):
    # 登入帳號使用 Email
    email: EmailStr
    # 登入密碼
    password: str

# ==============================
# 老師申請資料驗證模型

# 老師的教學地區
class TeacherLocation(BaseModel):
    city: str = Field(min_length=1, max_length=20)
    district: str = Field(min_length=1, max_length=20)

# 老師的授課時段
class TeacherAvailability(BaseModel):
    day: int = Field(ge=1, le=7)
    period: Literal["morning", "afternoon", "evening"]

# 成為家教老師的申請資料
class TeacherCreate(BaseModel):

    # 基本資料
    name: str = Field(min_length=1, max_length=50)
    gender: str | None = Field(default=None, max_length=10)

    # 教學資訊
    subjects: list[str] = Field(min_length=1)
    grades: list[str] = Field(min_length=1)

    hourly_rate: int = Field(gt=0)

    education: str | None = Field(default=None, max_length=255)
    experience: Decimal | None = Field(default=None, ge=0, le=999.9)

    intro: str | None = None

    # 多個教學地區
    locations: list[TeacherLocation] = Field(min_length=1)

    # 授課時段
    availability: list[TeacherAvailability] = Field(default_factory=list)

# ==============================
# 私訊資料驗證模型
# 傳送第一則私訊給老師時使用
class MessageCreate(BaseModel):

    # 收件老師的 ID（teachers.id）
    teacher_id: int = Field(gt=0)

    # 訊息內容：至少 1 個字元，最多 2000 個字元
    content: str = Field(min_length=1, max_length=2000)

# 在既有對話中傳送訊息時使用
class ConversationMessageRequest(BaseModel):

    # 訊息內容：至少 1 個字元，最多 2000 個字元
    content: str = Field(min_length=1, max_length=2000)

# ==============================
# 家教預約資料驗證模型
class BookingCreate(BaseModel):

    # 被預約的老師 ID（teachers.id）
    teacher_id: int = Field(gt=0)

    # 預約科目
    subject: str = Field(min_length=1, max_length=100)

    # 實際上課日期
    booking_date: date

    # 上課開始時間
    start_time: time

    # 課程長度：60、90、120 分鐘
    duration_minutes: Literal[60, 90, 120]

# ==============================
# 產生 JWT Token
def create_access_token(user_id: int):

    # 計算 Token 的到期時間
    # 使用 UTC 時間，避免時區差異
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_EXPIRE_MINUTES
    )

    # JWT Payload：Token 中攜帶的資料
    payload = {
        # sub (subject)：代表這個 Token 屬於哪位會員
        # JWT 的 sub 使用字串儲存會員 ID
        "sub": str(user_id),

        # exp (expiration)：Token 的到期時間
        "exp": expire
    }

    # 使用密鑰及指定演算法簽署 JWT
    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    # 回傳產生的 JWT Token
    return token

# ==============================
# 驗證 JWT Token

# Depends(bearer_scheme)：
# FastAPI 會自動從 Authorization Header 取得 Token
def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):

    # 取得 Bearer 後面的 JWT 字串
    token = credentials.credentials

    try:
        # 解碼並驗證 JWT
        # 會檢查簽章是否正確，以及 Token 是否過期
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        # 取得 Payload 裡面的會員 ID
        user_id = payload.get("sub")

        # 確認會員 ID 是由數字組成的字串
        # 避免缺少 sub 或資料格式錯誤
        if not isinstance(user_id, str) or not user_id.isdigit():
            raise HTTPException(
                status_code=401,
                detail="無效的登入憑證"
            )

        # 將會員 ID 轉成整數
        user_id = int(user_id)

        # 確認會員帳號仍然存在，且尚未刪除
        conn = get_db_connection()
        cursor = None

        try:
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s
                AND deleted_at IS NULL
                """,
                (user_id,)
            )

            user = cursor.fetchone()

        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

        # 帳號不存在或已刪除，拒絕使用舊 Token
        if not user:
            raise HTTPException(
                status_code=401,
                detail="會員帳號不存在或已刪除"
            )

        return user_id

    # JWT 簽章錯誤、過期或格式不正確時
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="登入憑證無效或已過期",
            headers={"WWW-Authenticate": "Bearer"}
        )

# ==============================
# MySQL 資料庫連線
def get_db_connection():

    # 建立 MySQL 連線
    # 連線資訊從 .env 取得，避免將密碼寫死在程式中
    return mysql.connector.connect(

        # 資料庫主機
        # 本機透過 SSH Tunnel 時使用 127.0.0.1
        host=os.getenv("DB_HOST"),

        # MySQL Port
        # 本機 SSH Tunnel 使用 3307
        # EC2 直接連線 RDS 時通常使用 3306
        port=int(os.getenv("DB_PORT", "3306")),
        # 資料庫帳號
        user=os.getenv("DB_USER"),
        # 資料庫密碼
        password=os.getenv("DB_PASSWORD"),
        # 資料庫名稱
        database=os.getenv("DB_NAME"),

        # 允許使用 SSL/TLS 連線（不代表強制驗證伺服器憑證）
        ssl_disabled=False,

        # 連線逾時設定，單位為秒
        connection_timeout=5,
    )

# ==============================
# 會員註冊 API

# POST /api/auth/register
# 使用者提供姓名、Email、密碼後建立會員
# 註冊成功回傳 HTTP 201 Created
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED, tags=["02｜會員管理 Auth"])
def register(user: UserRegister):

    connection = None
    cursor = None

    try:
        # 連接資料庫
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 根據 Email 查詢是否已有會員
        # %s 是 SQL 參數佔位符，可避免 SQL Injection
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (str(user.email),)
        )

        # 如果查得到資料，表示 Email 已經註冊
        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="此 Email 已經註冊"
            )

        # 將明文密碼轉換成 Argon2 雜湊值
        # 資料庫只儲存 password_hash，不儲存明文密碼
        hashed_password = password_hash.hash(user.password)

        # 新會員註冊時，一律設定為 student
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (user.name, str(user.email), hashed_password, "student")
        )

        # 提交交易，將新增資料正式寫入 MySQL
        connection.commit()

        # 回傳註冊成功訊息及會員基本資料
        # 不回傳密碼或密碼雜湊值
        return {
            "message": "註冊成功",
            "user": {

                # lastrowid：剛新增的會員 ID
                "id": cursor.lastrowid,

                "name": user.name,
                "email": str(user.email),
                "role": "student"
            }
        }

    # 已經主動產生的 HTTPException 直接往外拋出
    except HTTPException:
        raise

    # 避免同時註冊相同 Email 時違反 UNIQUE 限制
    except mysql.connector.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="此 Email 已經註冊"
        )

    # 其他 MySQL 操作錯誤
    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        # 關閉 Cursor
        if cursor is not None:
            cursor.close()

        # 關閉 MySQL 連線
        if connection is not None and connection.is_connected():
            connection.close()


# ==============================
# 會員登入 API

# POST /api/auth/login
# 使用 Email 和密碼登入
# 驗證成功後回傳 JWT Token
@app.post("/api/auth/login", tags=["02｜會員管理 Auth"])
def login(user: UserLogin):

    connection = None
    cursor = None

    try:
        # 連接 MySQL
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 根據 Email 查詢會員
        # 必須取得 password_hash，才能驗證密碼
        cursor.execute(
            """
            SELECT id, name, email, password_hash, role
            FROM users
            WHERE email = %s
            AND deleted_at IS NULL
            """,
            (str(user.email),)
        )

        # 取得查詢到的會員
        # 如果沒有這個 Email，會得到 None
        db_user = cursor.fetchone()

        # 驗證會員是否存在，以及密碼是否正確
        # password_hash.verify() 會將輸入密碼
        # 與資料庫中的 Argon2 雜湊值進行驗證
        if not db_user or not password_hash.verify(
            user.password, db_user["password_hash"]
        ):
            raise HTTPException(
                status_code=401,
                detail="Email 或密碼錯誤"
            )

        # 密碼正確後，根據會員 ID 產生 JWT
        access_token = create_access_token(db_user["id"])

        # 回傳 JWT 和會員基本資料
        # 前端之後可以使用 Token 呼叫需要登入的 API
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": db_user["id"],
                "name": db_user["name"],
                "email": db_user["email"],
                "role": db_user["role"]
            }
        }

    # 保留原本的 HTTP 錯誤，例如 401
    except HTTPException:
        raise

    # 資料庫連線或查詢發生錯誤
    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        # 關閉 Cursor
        if cursor is not None:
            cursor.close()

        # 關閉 MySQL 連線
        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得目前登入會員的資料

# GET /api/auth/me
# 必須提供有效的 JWT Token 才能使用
@app.get("/api/auth/me", tags=["02｜會員管理 Auth"])
def get_current_user(user_id: int = Depends(get_current_user_id)):

    connection = None
    cursor = None

    try:
        # 連接 MySQL
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 根據 JWT 中的會員 ID 查詢會員資料
        cursor.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        # 取得會員資料
        user = cursor.fetchone()

        # 如果會員已被刪除或不存在
        if not user:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 回傳會員基本資料，不包含密碼
        return {
            "user": user
        }

    # 保留原本的 HTTP 錯誤
    except HTTPException:
        raise

    # 處理資料庫錯誤
    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        # 關閉 Cursor
        if cursor is not None:
            cursor.close()

        # 關閉資料庫連線
        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 刪除目前登入會員的帳號
# DELETE /api/auth/me

@app.delete("/api/auth/me", tags=["02｜會員管理 Auth"])
def delete_my_account(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認會員存在並鎖定資料
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE id = %s
            AND deleted_at IS NULL
            FOR UPDATE
            """,
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 清除會員自己收藏的老師
        # 軟刪除不會觸發 favorites 的 ON DELETE CASCADE
        cursor.execute(
            """
            DELETE FROM favorites
            WHERE user_id = %s
            """,
            (user_id,)
        )

        # 2. 查詢會員是否有老師資料
        cursor.execute(
            """
            SELECT id, photo_key
            FROM teachers
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,)
        )

        teacher = cursor.fetchone()
        photo_key = None

        # 3. 如果有老師資料，先刪除老師資料
        if teacher:
            photo_key = teacher["photo_key"]

            cursor.execute(
                """
                DELETE FROM teachers
                WHERE id = %s AND user_id = %s
                """,
                (teacher["id"], user_id)
            )

            # teacher_locations 與 teacher_availability
            # 會透過 ON DELETE CASCADE 自動刪除

        # 4. 軟刪除會員帳號，並釋放原本的 Email
        cursor.execute(
            """
            UPDATE users
            SET
                name = '已刪除的會員',
                email = CONCAT('deleted_', id, '@deleted.tutorlink.invalid'),
                password_hash = '',
                deleted_at = CURRENT_TIMESTAMP
            WHERE id = %s
            AND deleted_at IS NULL
            """,
            (user_id,)
        )

        # 5. 所有資料庫操作成功後才正式儲存
        connection.commit()

        # 6. MySQL 刪除成功後清理 S3 頭貼
        if photo_key:
            try:
                delete_teacher_photo(photo_key)
            except Exception:
                logging.exception(
                    "會員已刪除，但 S3 頭貼清理失敗：user_id=%s, photo_key=%s",
                    user_id,
                    photo_key
                )

        return {
            "message": "會員帳號刪除成功"
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="會員帳號刪除失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得全部家教老師資料

# GET /api/teachers
# 前端 teachers.js 會透過 fetch() 呼叫此 API
@app.get("/api/teachers", tags=["03｜老師資料 Teachers"])
def get_teachers():

    # 先將連線與 Cursor 設為 None
    # 確保 finally 可以安全判斷是否需要關閉
    connection = None
    cursor = None

    try:
        # 建立 MySQL 連線
        connection = get_db_connection()

        # dictionary=True：
        # 查詢結果以 Dictionary 形式回傳
        # 例如 {"id": 1, "name": "王老師"}
        cursor = connection.cursor(dictionary=True)

        # 查詢老師基本資料及多個教學地區
        cursor.execute("""
            SELECT
                t.id,
                t.name,
                t.gender,
                t.subjects,
                t.grades,

                -- 將資料庫欄位名稱轉成前端使用的 camelCase
                t.hourly_rate AS hourlyRate,

                t.education,
                t.experience,
                t.intro,

                -- 老師頭貼在 AWS S3 的儲存路徑
                t.photo_key,

                -- 將同一位老師的多個教學地區整理成 JSON 陣列
                (
                    SELECT JSON_ARRAYAGG(
                        JSON_OBJECT(
                            'city', tl.city,
                            'district', tl.district
                        )
                    )
                    FROM teacher_locations AS tl
                    WHERE tl.teacher_id = t.id
                ) AS locations

            FROM teachers AS t
            ORDER BY t.id
        """)

        # fetchall()：取得所有查詢結果
        teachers = cursor.fetchall()

        # 將 MySQL JSON 欄位轉成 Python List
        for teacher in teachers:

            # 教學科目、年級及地區都是 JSON 資料
            for field in ("subjects", "grades", "locations"):

                # 如果是 JSON 字串，轉成 Python List
                if isinstance(teacher[field], str):
                    teacher[field] = json.loads(teacher[field])

            # 如果老師尚未設定教學地區，回傳空陣列
            if teacher["locations"] is None:
                teacher["locations"] = []

            # 產生 AWS S3 老師頭貼讀取網址
            # 取得老師在 S3 的照片路徑
            photo_key = teacher.get("photo_key")

            # 有照片才產生暫時讀取網址
            # 沒有照片則回傳 None，讓前端顯示預設人物圖示
            teacher["photo_url"] = (
                get_teacher_photo_url(photo_key)
                if photo_key
                else None
            )

        # FastAPI 會將 Python List / Dictionary
        # 自動轉換成 JSON 回傳給前端
        return teachers

    # MySQL 連線或查詢失敗
    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="無法取得老師資料"
        )

    finally:
        # 不論查詢成功或失敗，都關閉 Cursor
        if cursor is not None:
            cursor.close()

        # 關閉資料庫連線，避免佔用連線資源
        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 申請成為家教老師

# POST /api/teachers
# 會員登入後，可以申請成為家教老師
@app.post("/api/teachers", status_code=status.HTTP_201_CREATED, tags=["03｜老師資料 Teachers"])
def create_teacher(
    teacher: TeacherCreate,
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        # 建立 MySQL 連線
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 確認登入會員是否存在
        # 不限制註冊身分，學生與老師皆可申請成為家教
        cursor.execute(
            """
            SELECT id, role
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        # 取得會員資料
        current_user = cursor.fetchone()

        # 確認會員仍然存在
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 檢查會員是否已經申請過老師
        cursor.execute(
            "SELECT id FROM teachers WHERE user_id = %s",
            (user_id,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="您已經申請成為家教老師"
            )

        # 新增老師基本資料
        cursor.execute(
            """
            INSERT INTO teachers (
                user_id,
                name,
                gender,
                subjects,
                grades,
                hourly_rate,
                education,
                experience,
                intro
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                teacher.name,
                teacher.gender,
                json.dumps(teacher.subjects, ensure_ascii=False),
                json.dumps(teacher.grades, ensure_ascii=False),
                teacher.hourly_rate,
                teacher.education,
                teacher.experience,
                teacher.intro
            )
        )

        # 取得剛建立的老師 ID
        teacher_id = cursor.lastrowid

        # 新增老師的多個教學地區
        # 避免重複地區造成 UNIQUE 限制錯誤
        locations = list(dict.fromkeys(
            (location.city, location.district)
            for location in teacher.locations
        ))

        cursor.executemany(
            """
            INSERT INTO teacher_locations (
                teacher_id,
                city,
                district
            )
            VALUES (%s, %s, %s)
            """,
            [
                (teacher_id, city, district)
                for city, district in locations
            ]
        )

        # 新增老師的授課時段
        # 避免同一星期、同一時段重複寫入
        availability = list(dict.fromkeys(
            (item.day, item.period)
            for item in teacher.availability
        ))

        if availability:
            cursor.executemany(
                """
                INSERT INTO teacher_availability (
                    teacher_id,
                    day,
                    period
                )
                VALUES (%s, %s, %s)
                """,
                [
                    (teacher_id, day, period)
                    for day, period in availability
                ]
            )

        # 老師資料建立成功後，自動升級會員身分
        cursor.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
            """,
            ("teacher", user_id)
        )

        # 正式儲存老師資料與會員身分
        connection.commit()

        return {
            "message": "老師申請成功",
            "teacher_id": teacher_id
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.IntegrityError:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="您已經申請成為家教老師，或資料違反唯一性限制"
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="老師申請失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得目前登入會員的老師資料
# GET /api/teachers/me

@app.get("/api/teachers/me", tags=["04｜老師管理 Teacher Management"])
def get_my_teacher_profile(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 根據登入會員的 ID，查詢老師資料
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                name,
                gender,
                subjects,
                grades,
                hourly_rate AS hourlyRate,
                education,
                experience,
                intro,
                photo_key
            FROM teachers
            WHERE user_id = %s
            """,
            (user_id,)
        )

        teacher = cursor.fetchone()

        # 尚未建立老師資料
        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="尚未建立老師資料"
            )

        teacher_id = teacher["id"]

        # 將 JSON 欄位轉換成陣列
        for field in ("subjects", "grades"):
            if isinstance(teacher[field], str):
                teacher[field] = json.loads(teacher[field])

        # Decimal 轉換成數字，方便前端使用
        if teacher["experience"] is not None:
            teacher["experience"] = float(teacher["experience"])

        # 查詢授課地區
        cursor.execute(
            """
            SELECT city, district
            FROM teacher_locations
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )
        teacher["locations"] = cursor.fetchall()

        # 查詢授課時段
        cursor.execute(
            """
            SELECT day, period
            FROM teacher_availability
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )
        teacher["availability"] = cursor.fetchall()

        # 產生 AWS S3 老師頭貼讀取網址
        # 從老師資料取得 S3 照片路徑
        photo_key = teacher.get("photo_key")

        # 有照片才產生暫時讀取網址
        teacher["photo_url"] = (
            get_teacher_photo_url(photo_key)
            if photo_key
            else None
        )

        return {"teacher": teacher}

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="無法取得老師個人資料"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得指定老師的詳細資料
# GET /api/teachers/{teacher_id}
# 前端 teacher-detail.js 會呼叫此 API

@app.get("/api/teachers/{teacher_id}", tags=["03｜老師資料 Teachers"])
def get_teacher_detail(teacher_id: int):

    connection = None
    cursor = None

    try:
        # 建立 MySQL 連線
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 根據老師 ID 查詢基本資料
        cursor.execute(
            """
            SELECT
                id,
                name,
                gender,
                subjects,
                grades,
                hourly_rate AS hourlyRate,
                education,
                experience,
                intro,
                photo_key
            FROM teachers
            WHERE id = %s
            """,
            (teacher_id,)
        )

        teacher = cursor.fetchone()

        # 找不到指定老師
        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這位老師"
            )

        # 將 JSON 字串轉換成 Python List
        for field in ("subjects", "grades"):
            if isinstance(teacher[field], str):
                teacher[field] = json.loads(teacher[field])

        # 將教學經驗轉換成數字
        if teacher["experience"] is not None:
            teacher["experience"] = float(teacher["experience"])

        # 查詢老師的授課地區
        cursor.execute(
            """
            SELECT city, district
            FROM teacher_locations
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )

        teacher["locations"] = cursor.fetchall()

        # 查詢老師的可授課時段
        cursor.execute(
            """
            SELECT day, period
            FROM teacher_availability
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )

        teacher["availability"] = cursor.fetchall()

        # 產生 AWS S3 頭貼暫時讀取網址
        photo_key = teacher.get("photo_key")

        teacher["photo_url"] = (
            get_teacher_photo_url(photo_key)
            if photo_key
            else None
        )

        # 回傳指定老師的完整資料
        return {"teacher": teacher}

    # 保留 404 等 HTTP 錯誤
    except HTTPException:
        raise

    # MySQL 查詢失敗
    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="無法取得老師詳細資料"
        )

    finally:
        # 關閉 Cursor
        if cursor is not None:
            cursor.close()

        # 關閉 MySQL 連線
        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 上傳或更新老師頭貼

@app.post("/api/teachers/me/photo", tags=["04｜老師管理 Teacher Management"])
async def upload_my_teacher_photo(
    photo: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id)
):
    # 允許的圖片格式
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp"
    }

    if photo.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="只允許上傳 JPG、PNG 或 WebP 圖片"
        )

    # 限制檔案大小為 5 MB
    max_size = 5 * 1024 * 1024
    photo_bytes = await photo.read(max_size + 1)

    if not photo_bytes:
        raise HTTPException(
            status_code=400,
            detail="照片不可為空"
        )

    if len(photo_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail="照片不可超過 5 MB"
        )

    # 驗證實際圖片格式，避免只修改副檔名或 MIME 類型
    import io
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(photo_bytes)) as image:
            actual_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="圖片檔案格式無效"
        )

    expected_formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP"
    }

    if actual_format != expected_formats[photo.content_type]:
        raise HTTPException(
            status_code=400,
            detail="圖片實際格式與檔案類型不符"
        )

    connection = None
    cursor = None
    new_photo_key = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 確認目前會員已建立老師資料
        cursor.execute(
            "SELECT id FROM teachers WHERE user_id = %s",
            (user_id,)
        )
        teacher = cursor.fetchone()

        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="請先建立老師資料，再上傳頭貼"
            )

        # 將照片上傳至 AWS S3
        new_photo_key = upload_teacher_photo(
            io.BytesIO(photo_bytes),
            photo.content_type
        )

        # 將 S3 物件路徑記錄到 MySQL
        cursor.execute(
            """
            UPDATE teachers
            SET photo_key = %s
            WHERE id = %s
            """,
            (new_photo_key, teacher["id"])
        )

        connection.commit()

        return {
            "message": "老師頭貼上傳成功",
            "photo_key": new_photo_key
        }

    except HTTPException:
        raise

    except (ClientError, BotoCoreError):
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=502,
            detail="AWS S3 照片上傳失敗"
        )

    except Exception:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail="老師頭貼儲存失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

        await photo.close()

# ==============================
# 更新目前登入會員的老師資料
# PUT /api/teachers/me

@app.put("/api/teachers/me", tags=["04｜老師管理 Teacher Management"])
def update_my_teacher_profile(
    teacher: TeacherCreate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認目前登入的會員仍然存在
        cursor.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 2. 找到這位會員自己的老師資料
        # FOR UPDATE：更新期間鎖定該筆老師資料
        cursor.execute(
            """
            SELECT id
            FROM teachers
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,)
        )

        current_teacher = cursor.fetchone()

        if current_teacher is None:
            raise HTTPException(
                status_code=404,
                detail="尚未建立老師資料"
            )

        teacher_id = current_teacher["id"]

        # 3. 更新老師基本資料與教學資訊
        cursor.execute(
            """
            UPDATE teachers
            SET
                name = %s,
                gender = %s,
                subjects = %s,
                grades = %s,
                hourly_rate = %s,
                education = %s,
                experience = %s,
                intro = %s
            WHERE id = %s
            """,
            (
                teacher.name,
                teacher.gender,
                json.dumps(teacher.subjects, ensure_ascii=False),
                json.dumps(teacher.grades, ensure_ascii=False),
                teacher.hourly_rate,
                teacher.education,
                teacher.experience,
                teacher.intro,
                teacher_id
            )
        )

        # 4. 更新教學地區
        # 先刪除舊地區，再寫入目前選擇的地區
        cursor.execute(
            """
            DELETE FROM teacher_locations
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )

        # 去除重複地區
        locations = list(dict.fromkeys(
            (location.city, location.district)
            for location in teacher.locations
        ))

        cursor.executemany(
            """
            INSERT INTO teacher_locations (
                teacher_id,
                city,
                district
            )
            VALUES (%s, %s, %s)
            """,
            [
                (teacher_id, city, district)
                for city, district in locations
            ]
        )

        # 5. 更新每週可授課時段
        # 先刪除舊時段，再寫入目前選擇的時段
        cursor.execute(
            """
            DELETE FROM teacher_availability
            WHERE teacher_id = %s
            """,
            (teacher_id,)
        )

        # 去除重複時段
        availability = list(dict.fromkeys(
            (item.day, item.period)
            for item in teacher.availability
        ))

        if availability:
            cursor.executemany(
                """
                INSERT INTO teacher_availability (
                    teacher_id,
                    day,
                    period
                )
                VALUES (%s, %s, %s)
                """,
                [
                    (teacher_id, day, period)
                    for day, period in availability
                ]
            )

        # 6. 全部更新成功後，才正式儲存
        connection.commit()

        return {
            "message": "老師資料更新成功",
            "teacher_id": teacher_id
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.IntegrityError:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="老師資料更新失敗，請確認資料是否重複"
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="老師資料更新失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 刪除目前登入會員的老師資料
# DELETE /api/teachers/me

@app.delete("/api/teachers/me", tags=["04｜老師管理 Teacher Management"])
def delete_my_teacher_profile(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認會員存在，並鎖定會員資料
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE id = %s
            FOR UPDATE
            """,
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 2. 查詢目前會員自己的老師資料
        cursor.execute(
            """
            SELECT id, photo_key
            FROM teachers
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,)
        )

        current_teacher = cursor.fetchone()

        if current_teacher is None:
            raise HTTPException(
                status_code=404,
                detail="尚未建立老師資料"
            )

        teacher_id = current_teacher["id"]
        photo_key = current_teacher["photo_key"]

        # 3. 刪除老師資料
        # 教學地區與授課時段會透過 CASCADE 自動刪除
        cursor.execute(
            """
            DELETE FROM teachers
            WHERE id = %s AND user_id = %s
            """,
            (teacher_id, user_id)
        )

        # 4. 將會員身分恢復為 student
        cursor.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
            """,
            ("student", user_id)
        )

        # 5. 所有資料庫操作成功後才正式儲存
        connection.commit()

        # 6. MySQL 刪除成功後，清理 AWS S3 頭貼
        if photo_key:
            try:
                delete_teacher_photo(photo_key)

            except Exception:
                logging.exception(
                    "老師資料已刪除，但 S3 頭貼清理失敗：teacher_id=%s, photo_key=%s",
                    teacher_id,
                    photo_key
                )

        return {
            "message": "老師資料刪除成功",
            "role": "student"
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="老師資料刪除失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 收藏老師
# POST /api/favorites/{teacher_id}

@app.post(
    "/api/favorites/{teacher_id}",
    status_code=status.HTTP_201_CREATED,
    tags=["05｜收藏老師 Favorites"]
)
def add_favorite(
    teacher_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認目前登入的會員仍然存在
        cursor.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 2. 確認老師存在
        cursor.execute(
            "SELECT id FROM teachers WHERE id = %s",
            (teacher_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這位老師"
            )

        # 3. 確認是否已收藏
        cursor.execute(
            """
            SELECT id
            FROM favorites
            WHERE user_id = %s AND teacher_id = %s
            """,
            (user_id, teacher_id)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="您已經收藏過這位老師"
            )

        # 4. 新增收藏紀錄
        cursor.execute(
            """
            INSERT INTO favorites (user_id, teacher_id)
            VALUES (%s, %s)
            """,
            (user_id, teacher_id)
        )

        connection.commit()

        return {
            "message": "收藏老師成功",
            "teacher_id": teacher_id
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.IntegrityError:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="無法重複收藏，或收藏資料已變更"
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="收藏老師失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取消收藏老師
# DELETE /api/favorites/{teacher_id}

@app.delete("/api/favorites/{teacher_id}", tags=["05｜收藏老師 Favorites"])
def remove_favorite(
    teacher_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # 只刪除目前登入會員自己的收藏紀錄
        cursor.execute(
            """
            DELETE FROM favorites
            WHERE user_id = %s AND teacher_id = %s
            """,
            (user_id, teacher_id)
        )

        # 沒有找到收藏紀錄
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="尚未收藏這位老師"
            )

        connection.commit()

        return {
            "message": "取消收藏成功",
            "teacher_id": teacher_id
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="取消收藏失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得我的收藏老師清單
# GET /api/favorites

@app.get("/api/favorites", tags=["05｜收藏老師 Favorites"])
def get_my_favorites(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 確認目前登入會員仍然存在
        cursor.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 查詢目前會員收藏的老師
        cursor.execute(
            """
            SELECT
                t.id,
                t.name,
                t.gender,
                t.subjects,
                t.grades,
                t.hourly_rate AS hourlyRate,
                t.education,
                t.experience,
                t.intro,
                t.photo_key,
                f.created_at AS favorited_at,

                (
                    SELECT JSON_ARRAYAGG(
                        JSON_OBJECT(
                            'city', tl.city,
                            'district', tl.district
                        )
                    )
                    FROM teacher_locations AS tl
                    WHERE tl.teacher_id = t.id
                ) AS locations

            FROM favorites AS f
            JOIN teachers AS t
                ON f.teacher_id = t.id

            WHERE f.user_id = %s
            ORDER BY f.created_at DESC, f.id DESC
            """,
            (user_id,)
        )

        teachers = cursor.fetchall()

        # 整理老師資料格式
        for teacher in teachers:

            for field in ("subjects", "grades", "locations"):
                if isinstance(teacher[field], str):
                    teacher[field] = json.loads(teacher[field])

            if teacher["locations"] is None:
                teacher["locations"] = []

            if teacher["experience"] is not None:
                teacher["experience"] = float(
                    teacher["experience"]
                )

            # 產生 S3 頭貼暫時讀取網址
            photo_key = teacher.get("photo_key")

            teacher["photo_url"] = (
                get_teacher_photo_url(photo_key)
                if photo_key
                else None
            )

        return {
            "teachers": teachers,
            "total": len(teachers)
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="無法取得收藏老師清單"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 查詢老師收藏狀態
# GET /api/favorites/{teacher_id}/status

@app.get("/api/favorites/{teacher_id}/status", tags=["05｜收藏老師 Favorites"])
def get_favorite_status(
    teacher_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id
            FROM favorites
            WHERE user_id = %s AND teacher_id = %s
            """,
            (user_id, teacher_id)
        )

        favorite = cursor.fetchone()

        return {
            "teacher_id": teacher_id,
            "is_favorited": favorite is not None
        }

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="查詢收藏狀態失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 建立或取得與指定老師的對話
# POST /api/conversations/teacher/{teacher_id}

@app.post("/api/conversations/teacher/{teacher_id}", tags=["06｜私訊 Messages"])
def get_or_create_teacher_conversation(
    teacher_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢老師對應的有效會員帳號
        cursor.execute(
            """
            SELECT t.user_id AS receiver_id
            FROM teachers AS t
            JOIN users AS u ON t.user_id = u.id
            WHERE t.id = %s
              AND u.deleted_at IS NULL
            """,
            (teacher_id,)
        )

        teacher = cursor.fetchone()

        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="找不到可聯絡的老師"
            )

        receiver_id = teacher["receiver_id"]

        # 不允許與自己建立對話
        if receiver_id == user_id:
            raise HTTPException(
                status_code=400,
                detail="不能聯絡自己"
            )

        # 統一會員 ID 排列順序
        user1_id = min(user_id, receiver_id)
        user2_id = max(user_id, receiver_id)

        # 已存在就沿用，否則建立新對話
        cursor.execute(
            """
            INSERT INTO conversations (user1_id, user2_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
            """,
            (user1_id, user2_id)
        )

        conversation_id = cursor.lastrowid

        connection.commit()

        return {
            "conversation_id": conversation_id
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="建立對話失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 傳送私訊
# POST /api/messages

@app.post(
    "/api/messages",
    status_code=status.HTTP_201_CREATED,
    tags=["06｜私訊 Messages"]
)
def send_message(
    message: MessageCreate,
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢收件老師對應的會員帳號
        cursor.execute(
            """
            SELECT
                t.id AS teacher_id,
                t.user_id AS receiver_id
            FROM teachers AS t
            JOIN users AS u ON t.user_id = u.id
            WHERE t.id = %s
              AND u.deleted_at IS NULL
            """,
            (message.teacher_id,)
        )

        teacher = cursor.fetchone()

        # 老師不存在，或沒有可接收私訊的會員帳號
        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="找不到可接收私訊的老師"
            )

        # 不允許傳訊息給自己
        if teacher["receiver_id"] == user_id:
            raise HTTPException(
                status_code=400,
                detail="不能傳送私訊給自己"
            )

        # 將兩位會員 ID 由小到大排列
        # 確保同一組會員只會有一筆對話
        user1_id = min(user_id, teacher["receiver_id"])
        user2_id = max(user_id, teacher["receiver_id"])

        # 建立對話；如果已存在，就取得原本的對話 ID
        # UNIQUE (user1_id, user2_id) 避免重複建立
        cursor.execute(
            """
            INSERT INTO conversations (user1_id, user2_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
            """,
            (user1_id, user2_id)
        )

        conversation_id = cursor.lastrowid

        # 將訊息寫入 messages 資料表
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content
            )
            VALUES (%s, %s, %s)
            """,
            (
                conversation_id,
                user_id,
                message.content
            )
        )

        # 取得剛新增的訊息 ID
        message_id = cursor.lastrowid

        # 更新對話的最後活動時間
        cursor.execute(
            """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (conversation_id,)
        )

        # 對話與訊息全部寫入成功後才提交交易
        connection.commit()

        # 暫時回傳查詢結果，尚未建立對話或儲存訊息
        return {
            "message": "私訊傳送成功",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "sender_id": user_id,
            "receiver_id": teacher["receiver_id"],
            "teacher_id": message.teacher_id,
            "content": message.content
        }

    except HTTPException:
        # 發生 HTTP 錯誤時，取消尚未提交的資料庫操作
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        # MySQL 操作失敗時，取消整筆交易
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="私訊傳送失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得指定對話的聊天紀錄
# GET /api/conversations/{conversation_id}/messages

@app.get("/api/conversations/{conversation_id}/messages", tags=["06｜私訊 Messages"])
def get_conversation_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認對話存在，且目前會員是對話參與者
        cursor.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = %s
              AND (user1_id = %s OR user2_id = %s)
            """,
            (conversation_id, user_id, user_id)
        )

        conversation = cursor.fetchone()

        # 對話不存在或會員沒有權限查看
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="找不到對話紀錄"
            )

        # 2. 取得這筆對話的所有訊息
        cursor.execute(
            """
            SELECT
                m.id,
                m.conversation_id,
                m.sender_id,
                m.content,
                m.message_type,
                m.booking_id,
                m.created_at,
                m.read_at,

                b.student_id AS booking_student_id,
                t.user_id AS booking_teacher_user_id,
                b.subject AS booking_subject,
                b.booking_date,
                b.start_time AS booking_start_time,
                b.end_time AS booking_end_time,
                b.duration_minutes AS booking_duration_minutes,
                b.total_amount AS booking_total_amount,
                b.status AS booking_status

            FROM messages AS m
            LEFT JOIN bookings AS b ON m.booking_id = b.id
            LEFT JOIN teachers AS t ON b.teacher_id = t.id
            WHERE m.conversation_id = %s
            ORDER BY m.created_at ASC, m.id ASC
            """,
            (conversation_id,)
        )

        messages = cursor.fetchall()

        # 將預約日期與時間轉換成 JSON 字串
        for message in messages:
            if message["message_type"] == "booking":
                message["booking_date"] = str(
                    message["booking_date"]
                )
                message["booking_start_time"] = str(
                    message["booking_start_time"]
                )
                message["booking_end_time"] = str(
                    message["booking_end_time"]
                )

        # 3. 回傳聊天紀錄
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "total": len(messages)
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="取得聊天紀錄失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 將指定對話中的收到訊息標記為已讀
# PATCH /api/conversations/{conversation_id}/read

@app.patch("/api/conversations/{conversation_id}/read", tags=["06｜私訊 Messages"])
def mark_conversation_as_read(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認對話存在，且目前會員是對話參與者
        cursor.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = %s
              AND (user1_id = %s OR user2_id = %s)
            """,
            (conversation_id, user_id, user_id)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="找不到對話紀錄"
            )

        # 2. 只將對方傳送、尚未讀取的訊息標記為已讀
        cursor.execute(
            """
            UPDATE messages
            SET read_at = CURRENT_TIMESTAMP
            WHERE conversation_id = %s
              AND sender_id != %s
              AND read_at IS NULL
            """,
            (conversation_id, user_id)
        )

        # 記錄本次更新的訊息數量
        updated_count = cursor.rowcount

        # 3. 正式儲存已讀狀態
        connection.commit()

        return {
            "message": "訊息已標記為已讀",
            "conversation_id": conversation_id,
            "updated_count": updated_count
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="更新訊息已讀狀態失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得目前登入會員的所有對話清單
# GET /api/conversations

@app.get("/api/conversations", tags=["06｜私訊 Messages"])
def get_my_conversations(
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 只查詢目前會員參與的對話
        cursor.execute(
            """
            SELECT
                c.id AS conversation_id,

                CASE
                    WHEN c.user1_id = %s THEN c.user2_id
                    ELSE c.user1_id
                END AS other_user_id,

                u.name AS other_user_name,

                (
                    SELECT m.content
                    FROM messages AS m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT 1
                ) AS last_message,

                (
                    SELECT m.created_at
                    FROM messages AS m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT 1
                ) AS last_message_at,

                (
                    SELECT COUNT(*)
                    FROM messages AS m
                    WHERE m.conversation_id = c.id
                      AND m.sender_id != %s
                      AND m.read_at IS NULL
                ) AS unread_count

            FROM conversations AS c

            JOIN users AS u
                ON u.id = CASE
                    WHEN c.user1_id = %s THEN c.user2_id
                    ELSE c.user1_id
                END

            WHERE c.user1_id = %s
               OR c.user2_id = %s

            ORDER BY last_message_at DESC, c.id DESC
            """,
            (user_id, user_id, user_id, user_id, user_id)
        )

        conversations = cursor.fetchall()

        return {
            "conversations": conversations,
            "total": len(conversations)
        }

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="取得對話清單失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 取得目前會員的未讀訊息數量
# GET /api/messages/unread-count

@app.get("/api/messages/unread-count", tags=["06｜私訊 Messages"])
def get_unread_message_count(
    user_id: int = Depends(get_current_user_id)
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 只計算目前會員參與的對話中，由對方發送且尚未讀取的訊息
        cursor.execute(
            """
            SELECT COUNT(*) AS unread_count
            FROM messages AS m
            JOIN conversations AS c
                ON m.conversation_id = c.id
            WHERE (c.user1_id = %s OR c.user2_id = %s)
              AND m.sender_id != %s
              AND m.read_at IS NULL
            """,
            (user_id, user_id, user_id)
        )

        result = cursor.fetchone()

        return {
            "unread_count": result["unread_count"]
        }

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="取得未讀訊息數量失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 在指定對話中傳送訊息
# POST /api/conversations/{conversation_id}/messages

@app.post(
    "/api/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    tags=["06｜私訊 Messages"]
)
def send_conversation_message(
    conversation_id: int,
    message: ConversationMessageRequest,
    user_id: int = Depends(get_current_user_id)
):

    # 1. 驗證訊息內容
    content = message.content.strip()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="訊息內容不能為空白"
        )

    if len(content) > 2000:
        raise HTTPException(
            status_code=400,
            detail="訊息內容不能超過 2000 字"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 2. 確認對話存在，且會員是對話參與者
        cursor.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = %s
              AND (user1_id = %s OR user2_id = %s)
            FOR UPDATE
            """,
            (conversation_id, user_id, user_id)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="找不到對話紀錄"
            )

        # 3. 新增聊天訊息
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content
            )
            VALUES (%s, %s, %s)
            """,
            (conversation_id, user_id, content)
        )

        # 取得新增訊息的 ID
        message_id = cursor.lastrowid

        # 4. 更新對話最後活動時間
        cursor.execute(
            """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (conversation_id,)
        )

        # 5. 全部成功後才提交交易
        connection.commit()

        # 6. 回傳傳送結果
        return {
            "message": "訊息傳送成功",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "sender_id": user_id,
            "content": content
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="訊息傳送失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# POST /api/bookings
# 學生提出預約申請

@app.post(
    "/api/bookings",
    status_code=status.HTTP_201_CREATED,
    tags=["07｜家教預約 Bookings"]
)

def create_booking(
    booking: BookingCreate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        # 建立 MySQL 連線
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 確認老師存在，並鎖定老師資料
        # 同一位老師的預約建立操作依序執行
        cursor.execute(
            """
            SELECT id, user_id, subjects, hourly_rate
            FROM teachers
            WHERE id = %s
            FOR UPDATE
            """,
            (booking.teacher_id,)
        )

        teacher = cursor.fetchone()

        # 找不到老師
        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這位老師"
            )

        # 禁止會員預約自己的老師資料
        if teacher["user_id"] == user_id:
            raise HTTPException(
                status_code=400,
                detail="不能預約自己的家教課程"
            )

        # ==============================
        # 驗證老師是否教授學生選擇的科目
        # 將 MySQL JSON 欄位轉成 Python List
        subjects = teacher["subjects"]

        if isinstance(subjects, str):
            subjects = json.loads(subjects)

        # 確認預約科目是否包含在老師的教學科目中
        if booking.subject not in subjects:
            raise HTTPException(
                status_code=400,
                detail="這位老師沒有提供該科目的教學"
            )

        # ==============================
        # 驗證預約日期與時間是否在未來
        # 取得台灣目前的日期與時間
        taiwan_now = datetime.now(
            timezone(timedelta(hours=8))
        )

        # 組合學生選擇的上課日期與開始時間
        booking_datetime = datetime.combine(
            booking.booking_date,
            booking.start_time
        ).replace(
            tzinfo=timezone(timedelta(hours=8))
        )

        # 不允許預約已經過去的時間
        if booking_datetime <= taiwan_now:
            raise HTTPException(
                status_code=400,
                detail="預約日期與時間必須晚於現在"
            )

        # ==============================
        # 驗證老師當天是否有開放授課
        # Python：星期一 = 0，星期日 = 6
        # TutorLink：星期一 = 1，星期日 = 7
        booking_day = booking.booking_date.isoweekday()

        # 查詢老師在指定星期的可授課時段
        cursor.execute(
            """
            SELECT period
            FROM teacher_availability
            WHERE teacher_id = %s
            AND day = %s
            """,
            (booking.teacher_id, booking_day)
        )

        available_periods = [
            row["period"]
            for row in cursor.fetchall()
        ]

        # 當天沒有任何開放時段
        if not available_periods:
            raise HTTPException(
                status_code=400,
                detail="這位老師在選擇的日期沒有開放授課"
            )

        # ==============================
        # 驗證上課時間與課程長度
        # 開始時間必須以 30 分鐘為單位
        if (
            booking.start_time.minute not in (0, 30)
            or booking.start_time.second != 0
            or booking.start_time.microsecond != 0
        ):
            raise HTTPException(
                status_code=400,
                detail="上課時間只能選擇整點或半點"
            )

        # 計算課程結束時間
        end_datetime = booking_datetime + timedelta(
            minutes=booking.duration_minutes
        )

        # 課程不得跨越隔天
        if end_datetime.date() != booking.booking_date:
            raise HTTPException(
                status_code=400,
                detail="課程結束時間不可跨日"
            )

        end_time = end_datetime.time()

        # 各授課時段的開始與結束時間
        period_ranges = {
            "morning": (time(8, 0), time(12, 0)),
            "afternoon": (time(12, 0), time(18, 0)),
            "evening": (time(18, 0), time(22, 0))
        }

        # 將老師開放的時段依開始時間排序
        available_ranges = sorted(
            [period_ranges[period] for period in available_periods]
        )

        # 合併連續的授課時段
        merged_ranges = []

        for start, end in available_ranges:
            if merged_ranges and start <= merged_ranges[-1][1]:
                previous_start, previous_end = merged_ranges[-1]

                merged_ranges[-1] = (
                    previous_start,
                    max(previous_end, end)
                )
            else:
                merged_ranges.append((start, end))

        # 確認整堂課落在連續開放的授課時間內
        is_valid_time = any(
            booking.start_time >= start
            and end_time <= end
            for start, end in merged_ranges
        )

        if not is_valid_time:
            raise HTTPException(
                status_code=400,
                detail="預約時間超出老師開放的授課時段"
            )

        # ==============================
        # 計算課程總金額
        # 從資料庫取得老師每小時收費
        hourly_rate = teacher["hourly_rate"]

        # 根據課程分鐘數計算總金額
        total_amount = (
            hourly_rate * booking.duration_minutes
        ) // 60

        # ==============================
        # 取得預約對應的私訊聊天室
        # 老師對應的會員 ID
        teacher_user_id = teacher["user_id"]

        # 將學生與老師的會員 ID 由小到大排列
        user1_id = min(user_id, teacher_user_id)
        user2_id = max(user_id, teacher_user_id)

        # 已有聊天室就沿用，否則建立新聊天室
        cursor.execute(
            """
            INSERT INTO conversations (user1_id, user2_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
            """,
            (user1_id, user2_id)
        )

        # 取得聊天室 ID
        conversation_id = cursor.lastrowid

        # ==============================
        # 檢查是否重複提出預約申請
        cursor.execute(
            """
            SELECT id
            FROM bookings
            WHERE student_id = %s
            AND teacher_id = %s
            AND booking_date = %s
            AND start_time < %s
            AND end_time > %s
            AND status IN ('pending', 'accepted')
            LIMIT 1
            """,
            (
                user_id,
                booking.teacher_id,
                booking.booking_date,
                end_time,
                booking.start_time
            )
        )

        existing_booking = cursor.fetchone()

        if existing_booking:
            raise HTTPException(
                status_code=409,
                detail="你已經向這位老師申請過相同或重疊的預約時段"
            )

        # ==============================
        # 檢查老師是否已有確定的預約
        cursor.execute(
            """
            SELECT id
            FROM bookings
            WHERE teacher_id = %s
            AND booking_date = %s
            AND start_time < %s
            AND end_time > %s
            AND status = 'accepted'
            LIMIT 1
            """,
            (
                booking.teacher_id,
                booking.booking_date,
                end_time,
                booking.start_time
            )
        )

        accepted_booking = cursor.fetchone()

        if accepted_booking:
            raise HTTPException(
                status_code=409,
                detail="老師在這個時段已有確定的預約，請選擇其他時間"
            )

        # ==============================
        # 新增預約申請
        cursor.execute(
            """
            INSERT INTO bookings (
                student_id,
                teacher_id,
                conversation_id,
                subject,
                booking_date,
                start_time,
                end_time,
                duration_minutes,
                hourly_rate,
                total_amount,
                status
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, 'pending'
            )
            """,
            (
                user_id,
                booking.teacher_id,
                conversation_id,
                booking.subject,
                booking.booking_date,
                booking.start_time,
                end_time,
                booking.duration_minutes,
                hourly_rate,
                total_amount
            )
        )

        # 取得新增的預約 ID
        booking_id = cursor.lastrowid

        # 家教預約系統
        # 建立預約卡片訊息
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content,
                message_type,
                booking_id
            )
            VALUES (%s, %s, %s, 'booking', %s)
            """,
            (
                conversation_id,
                user_id,
                "提出了一筆家教預約申請",
                booking_id
            )
        )

        # 聊天室與預約資料一起儲存
        connection.commit()

        # 暫時回傳測試資料
        return {
            "message": "預約申請已送出",
            "booking_id": booking_id,
            "student_id": user_id,
            "teacher_id": booking.teacher_id,
            "conversation_id": conversation_id,
            "subject": booking.subject,
            "booking_date": str(booking.booking_date),
            "start_time": str(booking.start_time),
            "end_time": str(end_time),
            "duration_minutes": booking.duration_minutes,
            "hourly_rate": hourly_rate,
            "total_amount": total_amount,
            "status": "pending"
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# GET /api/bookings/me
# 查詢目前登入會員的預約紀錄（學生／老師）

@app.get("/api/bookings/me", tags=["07｜家教預約 Bookings"])
def get_my_bookings(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢自己作為學生或老師的所有預約
        cursor.execute(
            """
            SELECT
                b.id,
                b.student_id,
                b.teacher_id,
                b.conversation_id,
                b.subject,
                b.booking_date,
                b.start_time,
                b.end_time,
                b.duration_minutes,
                b.hourly_rate,
                b.total_amount,
                b.status,
                b.created_at,
                b.updated_at,

                u.name AS student_name,
                t.name AS teacher_name

            FROM bookings AS b

            JOIN teachers AS t
                ON b.teacher_id = t.id

            JOIN users AS u
                ON b.student_id = u.id

            WHERE
                b.student_id = %s
                OR t.user_id = %s

            ORDER BY b.booking_date DESC, b.start_time DESC
            """,
            (user_id, user_id)
        )

        bookings = cursor.fetchall()

        # 將日期與時間轉換成 JSON 可使用的字串
        for booking in bookings:
            booking["booking_date"] = str(
                booking["booking_date"]
            )
            booking["start_time"] = str(
                booking["start_time"]
            )
            booking["end_time"] = str(
                booking["end_time"]
            )
            booking["created_at"] = (
                booking["created_at"].isoformat()
            )
            booking["updated_at"] = (
                booking["updated_at"].isoformat()
            )

        return {
            "bookings": bookings
        }

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# PATCH /api/bookings/{booking_id}/accept
# 老師接受學生的預約申請

@app.patch("/api/bookings/{booking_id}/accept", tags=["07｜家教預約 Bookings"])
def accept_booking(
    booking_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ==============================
        # 鎖定老師紀錄，避免同時接受衝突預約
        # 先取得這筆預約對應的老師 ID
        cursor.execute(
            """
            SELECT teacher_id
            FROM bookings
            WHERE id = %s
            """,
            (booking_id,)
        )

        booking_info = cursor.fetchone()

        if booking_info is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 鎖定老師紀錄
        # 同一位老師的接受預約操作必須依序執行
        cursor.execute(
            """
            SELECT id
            FROM teachers
            WHERE id = %s
            FOR UPDATE
            """,
            (booking_info["teacher_id"],)
        )

        locked_teacher = cursor.fetchone()

        if locked_teacher is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這位老師"
            )

        # 查詢預約及對應老師的會員 ID
        cursor.execute(
            """
            SELECT
                b.id,
                b.teacher_id,
                b.conversation_id,
                b.status,
                b.booking_date,
                b.start_time,
                b.end_time,
                t.user_id AS teacher_user_id
            FROM bookings AS b
            JOIN teachers AS t
                ON b.teacher_id = t.id
            WHERE b.id = %s
            FOR UPDATE
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        # 預約不存在
        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 只有被預約的老師本人可以接受
        if booking["teacher_user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有被預約的老師可以接受這筆預約"
            )

        # ==============================
        # 檢查預約狀態
        if booking["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="只有等待回覆的預約才能接受"
            )

        # ==============================
        # 檢查老師是否已有時間重疊的確定預約
        cursor.execute(
            """
            SELECT id
            FROM bookings
            WHERE teacher_id = %s
            AND booking_date = %s
            AND start_time < %s
            AND end_time > %s
            AND status = 'accepted'
            AND id != %s
            LIMIT 1
            FOR UPDATE
            """,
            (
                booking["teacher_id"],
                booking["booking_date"],
                booking["end_time"],
                booking["start_time"],
                booking_id
            )
        )

        conflicting_booking = cursor.fetchone()

        if conflicting_booking:
            raise HTTPException(
                status_code=409,
                detail="這個時段已有其他確定的預約，無法接受"
            )

        # ==============================
        # 正式接受預約申請
        cursor.execute(
            """
            UPDATE bookings
            SET status = 'accepted'
            WHERE id = %s
            AND status = 'pending'
            """,
            (booking_id,)
        )

        # 確認成功更新一筆預約
        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="預約狀態已變更，無法接受"
            )

        # 老師接受預約後，新增聊天室事件訊息
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content,
                message_type,
                booking_id
            )
            VALUES (%s, %s, %s, 'booking', %s)
            """,
            (
                booking["conversation_id"],
                user_id,
                "接受了一筆家教預約申請",
                booking_id
            )
        )

        # 提交交易並釋放鎖定
        connection.commit()

        return {
            "message": "已成功接受預約",
            "booking_id": booking_id,
            "status": "accepted"
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# PATCH /api/bookings/{booking_id}/reject
# 老師拒絕學生的預約申請

@app.patch("/api/bookings/{booking_id}/reject", tags=["07｜家教預約 Bookings"])
def reject_booking(
    booking_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢預約及對應老師的會員 ID
        cursor.execute(
            """
            SELECT
                b.id,
                b.status,
                b.conversation_id,
                t.user_id AS teacher_user_id
            FROM bookings AS b
            JOIN teachers AS t
                ON b.teacher_id = t.id
            WHERE b.id = %s
            FOR UPDATE
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        # 預約不存在
        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 只有被預約的老師本人可以拒絕
        if booking["teacher_user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有被預約的老師可以拒絕這筆預約"
            )

        # ==============================
        # 檢查預約狀態
        if booking["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="只有等待回覆的預約才能拒絕"
            )

        # ==============================
        # 正式拒絕預約申請
        cursor.execute(
            """
            UPDATE bookings
            SET status = 'rejected'
            WHERE id = %s
            AND status = 'pending'
            """,
            (booking_id,)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="預約狀態已變更，無法拒絕"
            )

        # 老師拒絕預約後，新增聊天室事件訊息
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content,
                message_type,
                booking_id
            )
            VALUES (%s, %s, %s, 'booking', %s)
            """,
            (
                booking["conversation_id"],
                user_id,
                "拒絕了一筆家教預約申請",
                booking_id
            )
        )

        # 同時儲存預約狀態與聊天室事件
        connection.commit()

        return {
            "message": "已成功拒絕預約",
            "booking_id": booking_id,
            "status": "rejected"
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# PATCH /api/bookings/{booking_id}/cancel
# 學生取消自己的預約申請

@app.patch("/api/bookings/{booking_id}/cancel", tags=["07｜家教預約 Bookings"])
def cancel_booking(
    booking_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢預約資料
        cursor.execute(
            """
            SELECT
                id,
                student_id,
                conversation_id,
                status,
                booking_date
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        # 預約不存在
        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 只有提出預約的學生可以取消
        if booking["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有提出預約的學生可以取消這筆預約"
            )

        # ==============================
        # 檢查預約是否可以取消
        if booking["status"] not in ("pending", "accepted"):
            raise HTTPException(
                status_code=409,
                detail="只有等待回覆或已接受的預約才能取消"
            )

        # ==============================
        # 檢查取消期限｜上課前一天 23:59 前
        # 取得台灣當地日期
        today = datetime.now(ZoneInfo("Asia/Taipei")).date()

        # 取得預約上課日期
        booking_date = booking["booking_date"]

        # 上課當天或已經過期，不允許學生自行取消
        if today >= booking_date:
            raise HTTPException(
                status_code=409,
                detail="已超過取消期限，請於上課前一天 23:59 前取消預約"
            )

        # ==============================
        # 正式取消預約
        cursor.execute(
            """
            UPDATE bookings
            SET status = 'cancelled'
            WHERE id = %s
            AND status IN ('pending', 'accepted')
            """,
            (booking_id,)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="預約狀態已變更，無法取消"
            )

        # 學生取消預約後，新增聊天室事件訊息
        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                sender_id,
                content,
                message_type,
                booking_id
            )
            VALUES (%s, %s, %s, 'booking', %s)
            """,
            (
                booking["conversation_id"],
                user_id,
                "取消了一筆家教預約",
                booking_id
            )
        )

        # 儲存取消結果及聊天室事件訊息
        connection.commit()

        return {
            "message": "已成功取消預約",
            "booking_id": booking_id,
            "status": "cancelled"
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 家教預約系統
# GET /api/bookings/{booking_id}
# 查詢單筆預約詳細資料（學生／老師）

@app.get("/api/bookings/{booking_id}", tags=["07｜家教預約 Bookings"])
def get_booking_detail(
    booking_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢預約及對應老師的會員 ID
        cursor.execute(
            """
            SELECT
                b.id,
                b.student_id,
                b.teacher_id,
                b.conversation_id,
                b.subject,
                b.booking_date,
                b.start_time,
                b.end_time,
                b.duration_minutes,
                b.hourly_rate,
                b.total_amount,
                b.status,
                b.created_at,
                b.updated_at,
                t.user_id AS teacher_user_id
            FROM bookings AS b
            JOIN teachers AS t
                ON b.teacher_id = t.id
            WHERE b.id = %s
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        # 預約不存在
        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 只有預約學生或被預約的老師可以查看
        if (
            booking["student_id"] != user_id
            and booking["teacher_user_id"] != user_id
        ):
            raise HTTPException(
                status_code=403,
                detail="你沒有權限查看這筆預約"
            )

        # 將日期與時間轉換成 JSON 字串
        booking["booking_date"] = str(booking["booking_date"])
        booking["start_time"] = str(booking["start_time"])
        booking["end_time"] = str(booking["end_time"])
        booking["created_at"] = booking["created_at"].isoformat()
        booking["updated_at"] = booking["updated_at"].isoformat()

        # 內部驗證使用的會員 ID 不需要回傳
        booking.pop("teacher_user_id")

        return {
            "booking": booking
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
