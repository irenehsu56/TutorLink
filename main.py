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
# 回傳純文字內容，用於回應綠界付款結果通知
from fastapi.responses import PlainTextResponse
# 使用 Jinja2 模板渲染 HTML，支援共用元件
from fastapi.templating import Jinja2Templates
# 提供 CSS、JavaScript、圖片等靜態檔案
from fastapi.staticfiles import StaticFiles
# Pydantic：驗證使用者傳入的資料格式
from pydantic import BaseModel, EmailStr, Field
# 密碼雜湊與驗證（目前使用 Argon2）
from pwdlib import PasswordHash
# 產生安全的隨機字串，用於建立綠界唯一交易訂單編號
import secrets
# SHA256 雜湊運算，用於產生綠界 CheckMacValue 驗證碼
import hashlib
# 取得 Unix 時間戳，用於綠界訂單查詢
import time as time_module
# 發送 HTTP 請求至綠界 QueryTradeInfo API
import requests
# URL 編碼與解析，用於綠界簽章及訂單查詢
from urllib.parse import quote_plus, parse_qsl

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
# 綠界 ECPay 第三方付款設定

# 綠界環境：stage 為 Sandbox 測試環境
ECPAY_ENV = os.getenv("ECPAY_ENV", "stage")

# 綠界商店代號
ECPAY_MERCHANT_ID = os.environ["ECPAY_MERCHANT_ID"]

# 綠界交易驗證金鑰
ECPAY_HASH_KEY = os.environ["ECPAY_HASH_KEY"]
ECPAY_HASH_IV = os.environ["ECPAY_HASH_IV"]

# 綠界付款網址
ECPAY_PAYMENT_URL = os.environ["ECPAY_PAYMENT_URL"]

# 避免設定錯誤而連接到非預期的付款環境
if ECPAY_ENV != "stage":
    raise RuntimeError("目前 TutorLink 僅支援綠界 Sandbox 測試環境")

if ECPAY_PAYMENT_URL != "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5":
    raise RuntimeError("綠界 Sandbox 付款網址設定錯誤")

# 綠界 Sandbox 訂單查詢 API
ECPAY_QUERY_URL = "https://payment-stage.ecpay.com.tw/Cashier/QueryTradeInfo/V5"

# ==============================
# 綠界 ECPay CheckMacValue 驗證碼工具
def generate_ecpay_check_mac_value(params: dict) -> str:
    """
    依照綠界全方位金流 SHA256 規則產生 CheckMacValue。
    可用於建立付款表單及後續驗證綠界通知。
    """

    # 1. 排除原本的 CheckMacValue
    data = {
        str(key): str(value)
        for key, value in params.items()
        if key.lower() != "checkmacvalue"
    }

    # 2. 依照參數名稱排序（不區分大小寫）
    sorted_items = sorted(
        data.items(),
        key=lambda item: item[0].lower()
    )

    # 3. 組合參數字串
    parameter_string = "&".join(
        f"{key}={value}"
        for key, value in sorted_items
    )

    # 4. 加入 HashKey 與 HashIV
    raw_string = (
        f"HashKey={ECPAY_HASH_KEY}"
        f"&{parameter_string}"
        f"&HashIV={ECPAY_HASH_IV}"
    )

    # 5. URL Encode
    encoded_string = quote_plus(
        raw_string,
        safe="-_.!*()"
    ).lower()

    # 6. 綠界指定的字元替換規則
    encoded_string = (
        encoded_string
        .replace("%2d", "-")
        .replace("%5f", "_")
        .replace("%2e", ".")
        .replace("%21", "!")
        .replace("%2a", "*")
        .replace("%28", "(")
        .replace("%29", ")")
    )

    # 7. SHA256 雜湊，轉成大寫
    return hashlib.sha256(
        encoded_string.encode("utf-8")
    ).hexdigest().upper()

# ==============================
# 綠界 ECPay Sandbox 訂單查詢工具
# QueryTradeInfo
def query_ecpay_trade_info(merchant_trade_no: str) -> dict:
    """
    向綠界查詢訂單交易狀態。

    僅負責查詢，不修改 payments 資料表。
    """

    # 1. 建立查詢參數
    params = {
        "MerchantID": ECPAY_MERCHANT_ID,
        "MerchantTradeNo": merchant_trade_no,
        "TimeStamp": str(int(time_module.time()))
    }

    # 2. 計算 CheckMacValue
    params["CheckMacValue"] = generate_ecpay_check_mac_value(params)

    # 3. 向綠界送出查詢
    response = requests.post(
        ECPAY_QUERY_URL,
        data=params,
        timeout=15
    )

    response.raise_for_status()

    # 4. 綠界回傳 URL-encoded 格式
    # 使用原始位元組解析，避免 HTTP 回應字元編碼判斷錯誤
    result = dict(
        parse_qsl(
            response.content.decode("latin-1"),
            keep_blank_values=True,
            encoding="utf-8",
            errors="strict"
        )
    )

    # 5. 驗證回傳資料的 CheckMacValue
    received_mac = result.get("CheckMacValue", "")

    if not received_mac:
        raise ValueError("綠界查詢結果缺少 CheckMacValue")

    expected_mac = generate_ecpay_check_mac_value(result)

    if not secrets.compare_digest(
        received_mac.upper(),
        expected_mac.upper()
    ):
        raise ValueError("綠界查詢結果 CheckMacValue 驗證失敗")

    # 6. 確認查詢結果屬於指定商店及訂單
    if result.get("MerchantID") != ECPAY_MERCHANT_ID:
        raise ValueError("綠界查詢結果 MerchantID 不一致")

    if result.get("MerchantTradeNo") != merchant_trade_no:
        raise ValueError("綠界查詢結果 MerchantTradeNo 不一致")

    return result

# ==============================
# 綠界 ECPay 付款參數產生工具
def build_ecpay_payment_params(
    merchant_trade_no: str,
    amount: int,
    merchant_trade_date: str
) -> dict:
    """
    建立綠界 Sandbox AioCheckOut V5 付款參數。
    此函式只產生資料，不會送出付款請求。
    """

    # 驗證訂單編號長度，綠界限制最多 20 字元
    if not merchant_trade_no or len(merchant_trade_no) > 20:
        raise ValueError("綠界交易訂單編號格式錯誤")

    # 驗證付款金額必須為正整數
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("綠界付款金額必須為正整數")

    # 建立付款表單參數
    params = {
        "MerchantID": ECPAY_MERCHANT_ID,
        "MerchantTradeNo": merchant_trade_no,
        "MerchantTradeDate": merchant_trade_date,
        "PaymentType": "aio",
        "TotalAmount": str(amount),
        "TradeDesc": "TutorLink tutoring lesson payment",
        "ItemName": "TutorLink tutoring lesson",
        "ReturnURL": "https://tutorlink.life/api/payments/ecpay/notify",
        "ChoosePayment": "Credit",
        "EncryptType": "1"
    }

    # 計算綠界 SHA256 驗證碼
    params["CheckMacValue"] = generate_ecpay_check_mac_value(params)

    return params

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

# GET /notifications.html
# 使用者進入通知中心頁面時，透過 Jinja2 模板渲染 notifications.html
@app.get("/notifications.html", tags=["01｜網站頁面 Pages"])
def notifications_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="notifications.html"
    )

# GET /profile.html
# 使用者進入個人資料頁面時，透過 Jinja2 模板渲染 profile.html
@app.get("/profile.html", tags=["01｜網站頁面 Pages"])
def profile_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profile.html"
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
# 會員修改密碼驗證模型
class UserPasswordUpdate(BaseModel):
    # 目前使用的密碼
    current_password: str

    # 新密碼：至少 8 個字元，最多 128 個字元
    new_password: str = Field(min_length=8, max_length=128)

    # 再次輸入新密碼
    confirm_password: str

# ==============================
# 修改會員基本資料驗證模型，學生與老師共用
class UserProfileUpdate(BaseModel):
    # 會員姓名：至少 1 個字元，最多 50 個字元
    name: str = Field(min_length=1, max_length=50)
    # 電子郵件：自動驗證 Email 格式
    email: EmailStr

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
# 學生課後評價資料驗證模型
class ReviewCreate(BaseModel):
    booking_id: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=200)

class ReviewReplyCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200)

class ReviewUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=200)

# ==============================
# 綠界付款資料驗證模型
class PaymentCreate(BaseModel):
    booking_id: int = Field(gt=0)

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
# 課程提醒共用函式
# 需使用呼叫端既有的資料庫交易
def create_course_notification(
    cursor,
    user_id: int,
    booking_id: int,
    event_type: str
):
    cursor.execute(
        """
        INSERT INTO course_notifications (
            user_id,
            booking_id,
            event_type,
            is_read
        )
        VALUES (%s, %s, %s, FALSE)
        """,
        (user_id, booking_id, event_type)
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
            SELECT
                id,
                name,
                email,
                role,
                photo_key
            FROM users
            WHERE id = %s
            AND deleted_at IS NULL
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

        # 產生會員頭貼的 S3 暫時讀取網址
        # 從資料庫取得會員頭貼的 S3 Key
        photo_key = user.get("photo_key")

        # 若會員有上傳頭貼，產生可供前端顯示的圖片網址
        # 若尚未上傳，則回傳 None，讓前端顯示預設頭像
        user["photo_url"] = (
            get_teacher_photo_url(photo_key)
            if photo_key
            else None
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
# 修改目前登入會員的基本資料
# PATCH /api/auth/me
@app.patch("/api/auth/me", tags=["02｜會員管理 Auth"])
def update_my_profile(
    data: UserProfileUpdate,
    user_id: int = Depends(get_current_user_id)
):
    # 清除姓名前後空白
    new_name = data.name.strip()
    new_email = str(data.email)

    # 不允許空白姓名
    if not new_name:
        raise HTTPException(
            status_code=422,
            detail="會員姓名不可為空白"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 確認會員存在並鎖定資料
        cursor.execute(
            """
            SELECT id, name, email, role, photo_key
            FROM users
            WHERE id = %s
              AND deleted_at IS NULL
            FOR UPDATE
            """,
            (user_id,)
        )

        current_user = cursor.fetchone()

        if current_user is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 2. 確認 Email 沒有被其他會員使用
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
              AND id <> %s
            LIMIT 1
            """,
            (new_email, user_id)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="此 Email 已經被其他會員使用"
            )

        # 3. 更新會員基本資料
        cursor.execute(
            """
            UPDATE users
            SET
                name = %s,
                email = %s
            WHERE id = %s
              AND deleted_at IS NULL
            """,
            (new_name, new_email, user_id)
        )

        # 4. 兩個欄位更新成功後提交
        connection.commit()

        # 5. 回傳更新後的會員資料
        return {
            "message": "會員資料更新成功",
            "user": {
                "id": current_user["id"],
                "name": new_name,
                "email": new_email,
                "role": current_user["role"],
                "photo_key": current_user["photo_key"]
            }
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
            detail="此 Email 已經被其他會員使用"
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("修改會員資料失敗")

        raise HTTPException(
            status_code=500,
            detail="會員資料更新失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 修改目前登入會員的密碼
# PATCH /api/auth/me/password
@app.patch("/api/auth/me/password", tags=["02｜會員管理 Auth"])
def update_my_password(
    data: UserPasswordUpdate,
    user_id: int = Depends(get_current_user_id)
):
    # 確認兩次輸入的新密碼一致
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="新密碼與確認密碼不一致"
        )

    # 不允許新密碼與舊密碼相同
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="新密碼不可與目前密碼相同"
        )

    connection = None
    cursor = None

    try:
        # 連接 MySQL
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 鎖定目前登入會員的資料
        cursor.execute(
            """
            SELECT id, password_hash
            FROM users
            WHERE id = %s
              AND deleted_at IS NULL
            FOR UPDATE
            """,
            (user_id,)
        )

        db_user = cursor.fetchone()

        # 確認會員仍然存在
        if db_user is None:
            raise HTTPException(
                status_code=401,
                detail="會員不存在或登入憑證已失效"
            )

        # 驗證目前密碼是否正確
        if not password_hash.verify(
            data.current_password,
            db_user["password_hash"]
        ):
            raise HTTPException(
                status_code=400,
                detail="目前密碼不正確"
            )

        # 再次確認新密碼不等於目前密碼
        if password_hash.verify(
            data.new_password,
            db_user["password_hash"]
        ):
            raise HTTPException(
                status_code=400,
                detail="新密碼不可與目前密碼相同"
            )

        # 將新密碼轉換成 Argon2 雜湊值
        new_password_hash = password_hash.hash(
            data.new_password
        )

        # 更新資料庫中的密碼雜湊值
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
              AND deleted_at IS NULL
            """,
            (new_password_hash, user_id)
        )

        # 確認更新成功
        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=500,
                detail="密碼更新失敗"
            )

        # 提交資料庫變更
        connection.commit()

        return {
            "message": "密碼修改成功"
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("修改會員密碼失敗")

        raise HTTPException(
            status_code=500,
            detail="密碼修改失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

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
# 上傳或更新會員頭貼（學生／老師共用）
@app.post("/api/auth/me/photo", tags=["02｜會員管理 Auth"])
async def upload_my_member_photo(
    photo: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id)
):
    import io
    from PIL import Image, UnidentifiedImageError

    allowed_types = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP"
    }

    try:
        if photo.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="只允許上傳 JPG、PNG 或 WebP 圖片"
            )

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

        try:
            with Image.open(io.BytesIO(photo_bytes)) as image:
                actual_format = image.format
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="圖片檔案格式無效"
            )

        if actual_format != allowed_types[photo.content_type]:
            raise HTTPException(
                status_code=400,
                detail="圖片實際格式與檔案類型不符"
            )

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # 鎖定目前會員，避免更新到失效帳號
            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s AND deleted_at IS NULL
                FOR UPDATE
                """,
                (user_id,)
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=401,
                    detail="會員不存在或已失效"
                )

            # 沿用原本的 S3 上傳工具
            new_photo_key = upload_teacher_photo(
                io.BytesIO(photo_bytes),
                photo.content_type
            )

            # 更新會員頭貼
            cursor.execute(
                """
                UPDATE users
                SET photo_key = %s
                WHERE id = %s
                """,
                (new_photo_key, user_id)
            )

            # 如果會員具有老師資料，同步更新公開頭貼
            cursor.execute(
                """
                UPDATE teachers
                SET photo_key = %s
                WHERE user_id = %s
                """,
                (new_photo_key, user_id)
            )

            connection.commit()

            return {
                "message": "會員頭貼上傳成功",
                "photo_key": new_photo_key
            }

        except HTTPException:
            if connection is not None:
                connection.rollback()
            raise

        except (ClientError, BotoCoreError):
            if connection is not None:
                connection.rollback()
            logging.exception("會員頭貼 S3 上傳失敗")
            raise HTTPException(
                status_code=502,
                detail="AWS S3 照片上傳失敗"
            )

        except Exception:
            if connection is not None:
                connection.rollback()
            logging.exception("會員頭貼儲存失敗")
            raise HTTPException(
                status_code=500,
                detail="會員頭貼儲存失敗"
            )

        finally:
            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

    finally:
        await photo.close()

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

        # 同步更新老師頭貼與會員頭貼
        # 1. 更新老師公開頭貼
        cursor.execute(
            """
            UPDATE teachers
            SET photo_key = %s
            WHERE id = %s
              AND user_id = %s
            """,
            (new_photo_key, teacher["id"], user_id)
        )

        # 2. 更新會員頭貼
        cursor.execute(
            """
            UPDATE users
            SET photo_key = %s
            WHERE id = %s
              AND deleted_at IS NULL
            """,
            (new_photo_key, user_id)
        )

        # 確認會員資料確實更新成功
        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=404,
                detail="找不到有效的會員資料"
            )

        # 3. 兩張資料表更新成功後一起提交
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

                -- 取得聊天對象的會員頭貼 Key
                u.photo_key AS other_user_photo_key,

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

        # 為每位聊天對象產生 S3 頭貼讀取網址
        for conversation in conversations:

            photo_key = conversation.pop(
                "other_user_photo_key",
                None
            )

            conversation["other_user_photo_url"] = (
                get_teacher_photo_url(photo_key)
                if photo_key
                else None
            )

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

        # 課程提醒：學生提出預約後通知老師
        create_course_notification(
            cursor=cursor,
            user_id=teacher_user_id,
            booking_id=booking_id,
            event_type="booking_created"
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
                b.completed_at,

                (
                    SELECT
                        CASE
                            -- 已有正常付款成功紀錄
                            WHEN SUM(p.status = 'paid') > 0 THEN 'paid'

                            -- 存在需要核對或退款的異常付款
                            WHEN SUM(p.status = 'refund_required') > 0
                                THEN 'refund_required'

                            -- 存在尚未完成的付款訂單
                            WHEN SUM(p.status = 'pending') > 0 THEN 'pending'

                            -- 有付款紀錄，但都沒有成功或待處理交易
                            WHEN COUNT(p.id) > 0 THEN 'failed'

                            -- 尚未建立任何付款訂單
                            ELSE 'unpaid'
                        END
                    FROM payments AS p
                    WHERE p.booking_id = b.id
                ) AS payment_status,

                u.name AS student_name,
                t.name AS teacher_name,

                CASE
                    WHEN r.id IS NOT NULL THEN TRUE
                    ELSE FALSE
                END AS has_review,

                r.id AS review_id,
                r.content AS review_content

            FROM bookings AS b

            JOIN teachers AS t
                ON b.teacher_id = t.id

            JOIN users AS u
                ON b.student_id = u.id

            LEFT JOIN reviews AS r
                ON r.student_id = b.student_id
                AND r.teacher_id = b.teacher_id

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
            # 確認目前登入會員是否為這筆預約的學生
            booking["is_student_booking"] = (
                int(booking["student_id"]) == user_id
            )
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
                b.student_id,
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

        # ==============================
        # 課程提醒：老師接受預約後通知學生
        create_course_notification(
            cursor=cursor,
            user_id=booking["student_id"],
            booking_id=booking_id,
            event_type="booking_accepted"
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
                b.student_id,
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

        # 課程提醒：老師拒絕預約後通知學生
        create_course_notification(
            cursor=cursor,
            user_id=booking["student_id"],
            booking_id=booking_id,
            event_type="booking_rejected"
        )

        # 同時儲存預約狀態、聊天室事件與課程提醒
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
                b.id,
                b.student_id,
                b.conversation_id,
                b.status,
                b.booking_date,
                t.user_id AS teacher_user_id
            FROM bookings AS b
            JOIN teachers AS t ON t.id = b.teacher_id
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

        # 課程提醒：學生取消預約後通知老師
        create_course_notification(
            cursor=cursor,
            user_id=booking["teacher_user_id"],
            booking_id=booking_id,
            event_type="booking_cancelled"
        )

        # 同時儲存取消結果、聊天室事件及課程提醒
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

# ==============================
# 家教預約系統
# PATCH /api/bookings/{booking_id}/complete
# 老師確認課程已完成
@app.patch("/api/bookings/{booking_id}/complete", tags=["07｜家教預約 Bookings"])
def complete_booking(
    booking_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 鎖定預約，避免重複確認
        cursor.execute(
            """
            SELECT
                b.id,
                b.student_id,
                b.status,
                b.booking_date,
                b.end_time,
                b.completed_at,
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

        # 1. 預約是否存在
        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 2. 只有該筆預約的老師可以操作
        if booking["teacher_user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有該課程的老師可以確認完成"
            )

        # 3. 防止重複確認
        if booking["completed_at"] is not None:
            raise HTTPException(
                status_code=409,
                detail="這筆課程已經確認完成"
            )

        # 4. 必須是已接受的預約
        if booking["status"] != "accepted":
            raise HTTPException(
                status_code=409,
                detail="只有已接受的預約才能確認完成"
            )

        # 5. 以台灣時間判斷課程是否結束
        taiwan_now = datetime.now(
            ZoneInfo("Asia/Taipei")
        )

        booking_end = datetime.combine(
            booking["booking_date"],
            (
                datetime.min + booking["end_time"]
            ).time(),
            tzinfo=ZoneInfo("Asia/Taipei")
        )

        if taiwan_now < booking_end:
            raise HTTPException(
                status_code=409,
                detail="課程尚未結束，無法確認完成"
            )

        # 6. 寫入完成時間
        # 使用台灣當地時間儲存 DATETIME
        completed_at = taiwan_now.replace(tzinfo=None)

        cursor.execute(
            """
            UPDATE bookings
            SET completed_at = %s
            WHERE id = %s
              AND status = 'accepted'
              AND completed_at IS NULL
            """,
            (completed_at, booking_id)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="課程狀態已變更，請重新整理"
            )

        # 課程提醒：老師確認完成課程後通知學生
        create_course_notification(
            cursor=cursor,
            user_id=booking["student_id"],
            booking_id=booking_id,
            event_type="booking_completed"
        )

        # 評價通知：提醒學生課程已完成，可以發表評價
        cursor.execute(
            """
            INSERT INTO review_notifications (
                user_id,
                booking_id,
                review_id,
                event_type
            )
            VALUES (%s, %s, NULL, 'review_available')
            """,
            (
                booking["student_id"],
                booking_id
            )
        )

        # 課程完成狀態與兩種通知一起提交
        connection.commit()

        return {
            "message": "課程已確認完成",
            "booking_id": booking_id,
            "status": "accepted",
            "completed_at": completed_at.isoformat()
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
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 學生課後評價系統
# POST /api/reviews
# 學生針對已完成課程發表文字評價
@app.post(
    "/api/reviews",
    status_code=status.HTTP_201_CREATED,
    tags=["08｜課後評價 Reviews"]
)
def create_review(
    review: ReviewCreate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 移除前後空白，避免空白評價
        content = review.content.strip()

        if not content:
            raise HTTPException(
                status_code=422,
                detail="評價內容不能為空白"
            )

        # 2. 鎖定預約，確認學生身分及課程狀態
        cursor.execute(
            """
            SELECT
                id,
                student_id,
                teacher_id,
                status,
                completed_at
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (review.booking_id,)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 3. 只能評價自己預約的課程
        if booking["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只能評價自己上過的課程"
            )

        # 4. 預約必須已接受
        if booking["status"] != "accepted":
            raise HTTPException(
                status_code=409,
                detail="這筆預約尚未符合評價資格"
            )

        # 5. 必須由老師確認完成課程
        if booking["completed_at"] is None:
            raise HTTPException(
                status_code=409,
                detail="老師尚未確認完成課程"
            )

        # 6. 同一位學生對同一位老師只能評價一次
        cursor.execute(
            """
            SELECT id
            FROM reviews
            WHERE student_id = %s
            AND teacher_id = %s
            LIMIT 1
            """,
            (
                user_id,
                booking["teacher_id"]
            )
        )

        existing_review = cursor.fetchone()

        if existing_review is not None:
            raise HTTPException(
                status_code=409,
                detail="你已經評價過這位老師，可以修改原本的評價"
            )

        # 7. 新增學生評價
        cursor.execute(
            """
            INSERT INTO reviews (
                booking_id,
                student_id,
                teacher_id,
                content
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                review.booking_id,
                user_id,
                booking["teacher_id"],
                content
            )
        )

        review_id = cursor.lastrowid

        # 評價通知：學生首次發表評價後通知老師
        # teachers.id 與 users.id 不同，必須取得老師對應的會員 ID
        cursor.execute(
            """
            SELECT user_id
            FROM teachers
            WHERE id = %s
            """,
            (booking["teacher_id"],)
        )

        teacher_record = cursor.fetchone()

        if teacher_record is None:
            raise HTTPException(
                status_code=500,
                detail="找不到老師對應的會員資料"
            )

        # 建立老師的未讀評價通知
        cursor.execute(
            """
            INSERT INTO review_notifications (
                user_id,
                booking_id,
                review_id,
                event_type
            )
            VALUES (%s, %s, %s, 'review_created')
            """,
            (
                teacher_record["user_id"],
                review.booking_id,
                review_id
            )
        )

        # 評價與通知一起提交，避免資料不同步
        connection.commit()

        return {
            "message": "評價發表成功",
            "review_id": review_id,
            "booking_id": review.booking_id,
            "student_id": user_id,
            "teacher_id": booking["teacher_id"],
            "content": content
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()

        if exc.errno == 1062:
            raise HTTPException(
                status_code=409,
                detail="你已經評價過這位老師，無法重複新增評價"
            )

        raise HTTPException(
            status_code=500,
            detail="評價資料儲存失敗"
        )

    except mysql.connector.Error:
        if connection is not None:
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
# 學生修改自己的課後評價
# PATCH /api/reviews/{review_id}
@app.patch("/api/reviews/{review_id}", tags=["08｜課後評價 Reviews"])
def update_review(
    review_id: int,
    review: ReviewUpdate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        content = review.content.strip()

        if not content:
            raise HTTPException(
                status_code=422,
                detail="評價內容不能為空白"
            )

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 鎖定評價，確認是否存在
        cursor.execute(
            """
            SELECT
                id,
                student_id,
                teacher_id,
                booking_id
            FROM reviews
            WHERE id = %s
            FOR UPDATE
            """,
            (review_id,)
        )

        existing_review = cursor.fetchone()

        if existing_review is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆評價"
            )

        # 2. 只有原本發表的學生可以修改
        if existing_review["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只能修改自己發表的評價"
            )

        # 3. 更新原本的評價
        cursor.execute(
            """
            UPDATE reviews
            SET
                content = %s,
                review_edited_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (content, review_id)
        )

        connection.commit()

        return {
            "message": "評價修改成功",
            "review_id": review_id,
            "booking_id": existing_review["booking_id"],
            "teacher_id": existing_review["teacher_id"],
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
            detail="修改評價失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 老師新增／修改學生課後評價回覆
# PATCH /api/reviews/{review_id}/reply
@app.patch("/api/reviews/{review_id}/reply", tags=["08｜課後評價 Reviews"])
def reply_to_review(
    review_id: int,
    reply: ReviewReplyCreate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        content = reply.content.strip()

        if not content:
            raise HTTPException(
                status_code=422,
                detail="回覆內容不能為空白"
            )

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 鎖定評價並查詢對應老師
        cursor.execute(
            """
            SELECT
                r.id,
                r.booking_id,
                r.student_id,
                r.teacher_id,
                r.teacher_reply,
                r.teacher_replied_at,
                r.teacher_reply_edited_at,
                t.user_id AS teacher_user_id
            FROM reviews AS r
            JOIN teachers AS t
                ON r.teacher_id = t.id
            WHERE r.id = %s
            FOR UPDATE
            """,
            (review_id,)
        )

        existing_review = cursor.fetchone()

        if existing_review is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆評價"
            )

        # 2. 只有該老師可以新增或修改回覆
        if existing_review["teacher_user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有該課程的老師可以回覆或修改回覆"
            )

        # 3. 判斷是第一次回覆還是編輯回覆
        is_edit = existing_review["teacher_reply"] is not None

        if is_edit:
            # 已有回覆：修改內容並記錄編輯時間
            cursor.execute(
                """
                UPDATE reviews
                SET
                    teacher_reply = %s,
                    teacher_reply_edited_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (content, review_id)
            )

            message = "老師回覆修改成功"

        else:
            # 第一次回覆：記錄首次回覆時間
            cursor.execute(
                """
                UPDATE reviews
                SET
                    teacher_reply = %s,
                    teacher_replied_at = NOW(),
                    teacher_reply_edited_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (content, review_id)
            )

            message = "老師回覆成功"

        # 評價通知：老師首次回覆時通知學生
        # 編輯既有回覆不重複通知
        if not is_edit:
            cursor.execute(
                """
                INSERT INTO review_notifications (
                    user_id,
                    booking_id,
                    review_id,
                    event_type
                )
                VALUES (%s, %s, %s, 'review_replied')
                """,
                (
                    existing_review["student_id"],
                    existing_review["booking_id"],
                    review_id
                )
            )

        # 老師回覆與通知一起提交
        connection.commit()

        return {
            "message": message,
            "review_id": review_id,
            "teacher_id": existing_review["teacher_id"],
            "teacher_reply": content,
            "is_edited": is_edit
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
            detail="資料庫操作失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 查詢指定老師的公開課後評價
# GET /api/teachers/{teacher_id}/reviews
@app.get("/api/teachers/{teacher_id}/reviews", tags=["08｜課後評價 Reviews"])
def get_teacher_reviews(teacher_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 確認老師存在
        cursor.execute(
            """
            SELECT id
            FROM teachers
            WHERE id = %s
            """,
            (teacher_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這位老師"
            )

        # 取得該老師所有公開評價
        cursor.execute(
            """
            SELECT
                r.id,
                r.booking_id,
                r.student_id,
                r.content,
                r.review_edited_at,
                r.teacher_reply,
                r.created_at,
                r.teacher_replied_at,
                r.teacher_reply_edited_at,
                CASE
                    WHEN u.deleted_at IS NOT NULL
                    THEN '已刪除的會員'
                    ELSE u.name
                END AS student_name
            FROM reviews AS r
            JOIN users AS u
                ON r.student_id = u.id
            WHERE r.teacher_id = %s
            ORDER BY r.created_at DESC, r.id DESC
            """,
            (teacher_id,)
        )

        reviews = cursor.fetchall()

        for review in reviews:
            date_fields = [
                "created_at",
                "review_edited_at",
                "teacher_replied_at",
                "teacher_reply_edited_at"
            ]

            for field in date_fields:
                if review[field] is not None:
                    review[field] = review[field].isoformat()

        return {
            "teacher_id": teacher_id,
            "total": len(reviews),
            "reviews": reviews
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="查詢老師評價失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 綠界付款系統
# POST /api/payments/create
# 學生建立付款訂單
@app.post("/api/payments/create", tags=["09｜第三方付款 Payments"])
def create_payment(
    payment: PaymentCreate,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 查詢預約資料並鎖定
        # 防止同一堂課同時建立多筆待付款訂單
        cursor.execute(
            """
            SELECT
                id,
                student_id,
                status,
                total_amount
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (payment.booking_id,)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到這筆預約"
            )

        # 2. 只有預約的學生本人可以付款
        if booking["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有預約學生本人可以付款"
            )

        # 3. 老師必須先接受預約
        if booking["status"] != "accepted":
            raise HTTPException(
                status_code=400,
                detail="老師尚未接受預約，無法付款"
            )

        # 4. 付款金額必須有效
        # 金額一律使用資料庫的 total_amount
        amount_decimal = Decimal(str(booking["total_amount"]))

        if (
            not amount_decimal.is_finite()
            or amount_decimal <= 0
            or amount_decimal != amount_decimal.to_integral_value()
        ):
            raise HTTPException(
                status_code=400,
                detail="課程付款金額無效"
            )

        amount = int(amount_decimal)

        # 5. 檢查是否已經付款成功
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE booking_id = %s
              AND status = 'paid'
            LIMIT 1
            """,
            (payment.booking_id,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="這堂課已經付款成功，無法重複付款"
            )

        # 5-1. 檢查是否存在需要核對或退款的異常付款
        # 避免學生在異常交易尚未處理前再次付款
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE booking_id = %s
              AND status = 'refund_required'
            LIMIT 1
            """,
            (payment.booking_id,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="這堂課存在異常付款紀錄，請聯絡客服確認，暫時無法再次付款"
            )

        # 6. 檢查同一堂課所有待付款訂單
        cursor.execute(
            """
            SELECT
                id,
                merchant_trade_no
            FROM payments
            WHERE booking_id = %s
            AND status = 'pending'
            ORDER BY id DESC
            """,
            (payment.booking_id,)
        )

        pending_payments = cursor.fetchall()

        for pending_payment in pending_payments:

            try:
                ecpay_result = query_ecpay_trade_info(
                    pending_payment["merchant_trade_no"]
                )

                # 取得綠界交易狀態
                trade_status = str(
                    ecpay_result.get("TradeStatus", "")
                ).strip()

                ecpay_trade_no = str(
                    ecpay_result.get("TradeNo", "")
                ).strip()

                # 只接受明確的已付款或未付款狀態
                if trade_status not in ("0", "1"):
                    logging.warning(
                        "ECPay unknown trade status: payment_id=%s, "
                        "TradeStatus=%s, HasTradeNo=%s",
                        pending_payment["id"],
                        trade_status,
                        bool(ecpay_trade_no)
                    )

                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "PAYMENT_QUERY_UNCONFIRMED",
                            "message": "無法確認上一筆付款交易狀態，請稍後再試。",
                            "payment_id": pending_payment["id"]
                        }
                    )

            except (requests.RequestException, ValueError):
                logging.exception("查詢既有綠界交易失敗")
                raise HTTPException(
                    status_code=502,
                    detail="暫時無法確認付款狀態，請稍後再試"
                )

            if trade_status == "1":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PAYMENT_ALREADY_PAID",
                        "message": "綠界顯示已有付款成功的交易，請等待狀態同步。"
                    }
                )

            if trade_status == "0":

                # 正式環境：維持防止重複付款的保護
                if ECPAY_ENV != "stage":
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "PAYMENT_RETRY_REQUIRED",
                            "message": "上一筆付款尚未完成，請稍後再試。",
                            "payment_id": pending_payment["id"]
                        }
                    )

                # Sandbox：允許建立新的付款嘗試
                # superseded 僅表示 TutorLink 不再使用這筆舊訂單
                # 不代表綠界交易已取消或失效

                cursor.execute(
                    """
                    UPDATE payments
                    SET status = 'superseded'
                    WHERE id = %s
                    AND booking_id = %s
                    AND status = 'pending'
                    """,
                    (
                        pending_payment["id"],
                        payment.booking_id
                    )
                )

                logging.warning(
                    "ECPay Sandbox payment superseded: old_payment_id=%s",
                    pending_payment["id"]
                )

                continue

            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PAYMENT_STATUS_UNKNOWN",
                    "message": "無法確認既有付款訂單的狀態，請稍後再試。"
                }
            )

        # 7. 產生唯一的綠界訂單編號
        # TL + 18 位隨機十六進位字元，共 20 字元
        merchant_trade_no = "TL" + secrets.token_hex(9).upper()

        # 使用台灣時區產生綠界交易日期
        # 格式：YYYY/MM/DD HH:MM:SS
        merchant_trade_date = datetime.now(
            ZoneInfo("Asia/Taipei")
        ).strftime("%Y/%m/%d %H:%M:%S")

        # 8. 建立付款紀錄
        cursor.execute(
            """
            INSERT INTO payments (
                booking_id,
                merchant_trade_no,
                merchant_trade_date,
                amount,
                status
            )
            VALUES (%s, %s, %s, %s, 'pending')
            """,
            (
                payment.booking_id,
                merchant_trade_no,
                datetime.strptime(
                    merchant_trade_date,
                    "%Y/%m/%d %H:%M:%S"
                ),
                amount
            )
        )

        payment_id = cursor.lastrowid

        # 使用新訂單資料產生綠界付款參數
        ecpay_params = build_ecpay_payment_params(
            merchant_trade_no=merchant_trade_no,
            amount=amount,
            merchant_trade_date=merchant_trade_date
        )

        connection.commit()

        return {
            "message": "付款訂單建立成功",
            "payment_id": payment_id,
            "booking_id": payment.booking_id,
            "merchant_trade_no": merchant_trade_no,
            "amount": amount,
            "status": "pending",
            "payment_url": ECPAY_PAYMENT_URL,
            "ecpay_params": ecpay_params
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("建立付款訂單失敗")

        raise HTTPException(
            status_code=500,
            detail="建立付款訂單失敗，請稍後再試"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 綠界付款系統
# GET /api/payments/{payment_id}/checkout
# 取得既有待付款訂單的綠界付款參數
@app.get("/api/payments/{payment_id}/checkout", tags=["09｜第三方付款 Payments"])
def get_existing_payment_checkout(
    payment_id: int,
    user_id: int = Depends(get_current_user_id)
):
    # 付款續付功能目前只開放 Sandbox 測試
    # 不再限制特定 payment_id
    if ECPAY_ENV != "stage":
        raise HTTPException(
            status_code=403,
            detail="目前僅開放 Sandbox 付款測試"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                p.id,
                p.booking_id,
                p.merchant_trade_no,
                p.merchant_trade_date,
                p.amount,
                p.status,
                b.student_id,
                b.status AS booking_status,
                b.total_amount
            FROM payments AS p
            JOIN bookings AS b
                ON b.id = p.booking_id
            WHERE p.id = %s
            """,
            (payment_id,)
        )

        payment = cursor.fetchone()

        if payment is None:
            raise HTTPException(
                status_code=404,
                detail="找不到付款訂單"
            )

        if payment["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="只有預約學生本人可以付款"
            )

        if payment["booking_status"] != "accepted":
            raise HTTPException(
                status_code=409,
                detail="預約狀態不允許付款"
            )

        if payment["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="此訂單不是待付款狀態"
            )

        if (
            Decimal(str(payment["amount"]))
            != Decimal(str(payment["total_amount"]))
        ):
            raise HTTPException(
                status_code=409,
                detail="付款金額與預約金額不一致"
            )

        # 檢查同一堂課是否已由其他訂單付款
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE booking_id = %s
              AND status = 'paid'
            LIMIT 1
            """,
            (payment["booking_id"],)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="這堂課已付款成功"
            )

        # 向綠界查詢一次交易狀態
        result = query_ecpay_trade_info(
            payment["merchant_trade_no"]
        )

        # Sandbox：確認查無交易時的回應欄位
        if ECPAY_ENV == "stage":
            logging.warning(
                "ECPay checkout response keys=%s",
                list(result.keys())
            )

        # 取得綠界查詢交易結果
        rtn_code = str(result.get("RtnCode", "")).strip()
        trade_status = str(result.get("TradeStatus", "")).strip()
        ecpay_trade_no = str(result.get("TradeNo", "")).strip()

        # 綠界查詢成功才允許判斷交易是否已付款
        # 查詢結果不明確時，禁止重新送出付款
        if trade_status not in ("0", "1"):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PAYMENT_QUERY_UNCONFIRMED",
                    "message": "無法確認綠界交易狀態，請稍後再試。",
                    "payment_id": payment_id
                }
            )

        # Sandbox 除錯資訊
        # 不記錄 CheckMacValue 或金流金鑰
        if ECPAY_ENV == "stage":
            logging.warning(
                "ECPay checkout payment_id=%s RtnCode=%s TradeStatus=%s HasTradeNo=%s",
                payment_id,
                rtn_code,
                trade_status,
                bool(ecpay_trade_no)
            )

        # 綠界顯示交易已付款成功
        if trade_status == "1":
            raise HTTPException(
                status_code=409,
                detail="綠界顯示此訂單已付款成功，請等待付款狀態同步"
            )

        # 綠界已存在交易，但尚未確認付款成功
        if trade_status == "0":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PAYMENT_STILL_ACTIVE",
                    "message": (
                        "綠界尚未確認這筆交易完成，"
                        "為避免重複付款，請稍後再試。"
                    ),
                    "payment_id": payment_id
                }
            )

        # 綠界查無交易紀錄
        # 僅在明確查無交易，且沒有綠界交易編號時允許續付
        if rtn_code == "10200047" and not ecpay_trade_no:
            logging.warning(
                "ECPay checkout retry allowed: payment_id=%s",
                payment_id
            )

        else:
            # 其他未知狀態一律禁止重新送出
            raise HTTPException(
                status_code=409,
                detail=(
                    "目前無法確認此訂單是否可以重新付款，"
                    "請勿重複送出交易"
                )
            )

        # 使用原始交易日期，不產生新訂單編號
        trade_date = payment["merchant_trade_date"].strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        ecpay_params = build_ecpay_payment_params(
            merchant_trade_no=payment["merchant_trade_no"],
            amount=int(payment["amount"]),
            merchant_trade_date=trade_date
        )

        return {
            "message": "取得既有付款訂單成功",
            "payment_id": payment["id"],
            "booking_id": payment["booking_id"],
            "merchant_trade_no": payment["merchant_trade_no"],
            "amount": int(payment["amount"]),
            "status": "pending",
            "payment_url": ECPAY_PAYMENT_URL,
            "ecpay_params": ecpay_params
        }

    except HTTPException:
        raise

    except (requests.RequestException, ValueError):
        logging.exception("查詢綠界付款訂單失敗")
        raise HTTPException(
            status_code=502,
            detail="無法確認綠界訂單狀態"
        )

    except mysql.connector.Error:
        logging.exception("取得既有付款訂單失敗")
        raise HTTPException(
            status_code=500,
            detail="取得付款訂單失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 綠界付款結果通知
# POST /api/payments/ecpay/notify
@app.post("/api/payments/ecpay/notify", tags=["09｜第三方付款 Payments"])
async def ecpay_payment_notify(request: Request):

    # 綠界 Sandbox：允許通過驗證的付款成功通知更新資料庫
    # 正式環境仍需另外完成安全性與付款流程測試
    ENABLE_ECPAY_PAYMENT_UPDATE = True

    def reply(message: str, status_code: int = 400):
        return PlainTextResponse(
            content=message,
            status_code=status_code
        )

    # 1. 讀取綠界 POST 表單
    try:
        form = await request.form()
        notify_data = dict(form)

        # 修正 UTF-8 中文被誤判為 Latin-1 的情況
        # 避免 RtnMsg 等中文欄位亂碼，造成 CheckMacValue 驗證失敗
        for key, value in notify_data.items():
            if isinstance(value, str):
                try:
                    notify_data[key] = value.encode("latin-1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass

    except Exception:
        logging.exception("讀取綠界付款通知失敗")
        return reply("0|InvalidForm")

    merchant_trade_no = notify_data.get("MerchantTradeNo", "")

    if not merchant_trade_no:
        return reply("0|InvalidOrder")

    # Sandbox 除錯：檢查可能影響簽章的通知欄位
    # 僅記錄指定欄位，不輸出完整付款通知或金鑰
    logging.warning(
        "ECPay 通知欄位檢查："
        "RtnMsg=%r, "
        "PaymentDate=%r, "
        "PaymentType=%r, "
        "PaymentTypeChargeFee=%r, "
        "SimulatePaid=%r",
        notify_data.get("RtnMsg"),
        notify_data.get("PaymentDate"),
        notify_data.get("PaymentType"),
        notify_data.get("PaymentTypeChargeFee"),
        notify_data.get("SimulatePaid")
    )

    # 2. 驗證簽章
    received_mac = notify_data.get("CheckMacValue", "")

    if not received_mac:
        return reply("0|InvalidCheckMacValue")

    try:
        expected_mac = generate_ecpay_check_mac_value(notify_data)
    except Exception:
        logging.exception("計算綠界通知簽章失敗")
        return reply("0|InvalidCheckMacValue")

    # 綠界付款通知簽章驗證
    # 若簽章不一致，記錄交易編號與驗證結果，方便 Sandbox 除錯
    if not secrets.compare_digest(
        received_mac.upper(),
        expected_mac.upper()
    ):
        logging.warning(
            "綠界付款通知簽章驗證失敗："
            "MerchantTradeNo=%s, "
            "ReceivedMac=%s, "
            "ExpectedMac=%s, "
            "Fields=%s",
            merchant_trade_no,
            received_mac,
            expected_mac,
            sorted(notify_data.keys())
        )

        return reply("0|InvalidCheckMacValue")

    # 3. 驗證商店代號
    if notify_data.get("MerchantID") != ECPAY_MERCHANT_ID:
        return reply("0|InvalidMerchantID")

    # 4. 驗證金額
    amount_text = str(notify_data.get("TradeAmt", ""))

    if not amount_text.isascii() or not amount_text.isdecimal():
        return reply("0|InvalidAmount")

    trade_amount = int(amount_text)

    if trade_amount <= 0:
        return reply("0|InvalidAmount")

    # 5. 驗證付款結果代碼
    rtn_code = str(notify_data.get("RtnCode", "")).strip()

    if not rtn_code.isascii() or not rtn_code.isdecimal():
        return reply("0|InvalidRtnCode")

    # 6. 驗證綠界交易編號
    ecpay_trade_no = str(notify_data.get("TradeNo", "")).strip()

    if (
        not ecpay_trade_no
        or len(ecpay_trade_no) > 30
        or not ecpay_trade_no.isascii()
        or not ecpay_trade_no.isalnum()
    ):
        return reply("0|InvalidTradeNo")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        connection.start_transaction()

        # 7. 先查詢付款紀錄所屬的預約 ID
        # 此時不鎖定 payments，避免與建立付款 API 的鎖定順序衝突
        cursor.execute(
            """
            SELECT booking_id
            FROM payments
            WHERE merchant_trade_no = %s
            """,
            (merchant_trade_no,)
        )

        payment_lookup = cursor.fetchone()

        if payment_lookup is None:
            return reply("0|OrderNotFound")

        # 8. 優先鎖定 bookings
        # 同時取得老師 ID，供付款成功提醒使用
        cursor.execute(
            """
            SELECT
                id,
                status,
                teacher_id
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (payment_lookup["booking_id"],)
        )

        locked_booking = cursor.fetchone()

        if locked_booking is None:
            return reply("0|BookingNotFound")

        # 9. 再鎖定 payments
        cursor.execute(
            """
            SELECT
                id,
                booking_id,
                merchant_trade_no,
                amount,
                status,
                ecpay_trade_no
            FROM payments
            WHERE merchant_trade_no = %s
            FOR UPDATE
            """,
            (merchant_trade_no,)
        )

        payment_record = cursor.fetchone()

        if payment_record is None:
            return reply("0|OrderNotFound")

        if int(payment_record["amount"]) != trade_amount:
            return reply("0|AmountMismatch")

        # 10. 檢查同一交易編號是否被其他訂單使用
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE ecpay_trade_no = %s
              AND id != %s
            LIMIT 1
            """,
            (
                ecpay_trade_no,
                payment_record["id"]
            )
        )

        if cursor.fetchone() is not None:
            return reply("0|DuplicateTradeNo")

        saved_trade_no = payment_record["ecpay_trade_no"]

        if (
            saved_trade_no is not None
            and saved_trade_no != ecpay_trade_no
        ):
            return reply("0|TradeNoMismatch")

        # 11. 已付款訂單：重複通知不再次更新
        if payment_record["status"] == "paid":

            if (
                rtn_code == "1"
                and saved_trade_no == ecpay_trade_no
            ):
                connection.commit()
                return reply("1|OK", 200)

            return reply("0|InvalidPaymentStatus")

        # 12. 已記錄的重複付款異常：避免重複處理
        if payment_record["status"] == "refund_required":

            if (
                rtn_code == "1"
                and saved_trade_no == ecpay_trade_no
            ):
                connection.commit()
                return reply("1|OK", 200)

            return reply("0|InvalidPaymentStatus")

        # 13. Sandbox 通知更新開關
        if not ENABLE_ECPAY_PAYMENT_UPDATE:
            logging.warning(
                "ECPay Sandbox 通知驗證結果："
                "MerchantTradeNo=%s, RtnCode=%s, TradeNo=%s",
                merchant_trade_no,
                rtn_code,
                ecpay_trade_no
            )
            return reply("0|NotVerified")

        # 14. 非成功通知：暫不認定最終失敗
        if rtn_code != "1":
            connection.commit()
            return reply("1|OK", 200)

        # 15. 允許 pending 與 superseded 接收成功通知
        if payment_record["status"] not in (
            "pending",
            "superseded"
        ):
            return reply("0|InvalidPaymentStatus")

        if payment_record["booking_id"] != locked_booking["id"]:
            return reply("0|BookingMismatch")

        # 16. 檢查同一堂課是否已經有成功付款
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE booking_id = %s
              AND status = 'paid'
              AND id != %s
            LIMIT 1
            """,
            (
                payment_record["booking_id"],
                payment_record["id"]
            )
        )

        existing_paid_payment = cursor.fetchone()

        if existing_paid_payment is not None:

            # 綠界已通知付款成功，但課程已由另一筆訂單付款
            # 保留異常交易，供人工核對及退款
            cursor.execute(
                """
                UPDATE payments
                SET
                    status = 'refund_required',
                    ecpay_trade_no = %s,
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                  AND status IN ('pending', 'superseded')
                """,
                (
                    ecpay_trade_no,
                    payment_record["id"]
                )
            )

            if cursor.rowcount != 1:
                return reply("0|UpdateFailed")

            connection.commit()

            logging.error(
                "ECPay duplicate payment requires review: "
                "booking_id=%s, incoming_payment_id=%s, "
                "existing_paid_payment_id=%s",
                payment_record["booking_id"],
                payment_record["id"],
                existing_paid_payment["id"]
            )

            return reply("1|OK", 200)

        # 16-1. 綠界付款成功，但預約已不是 accepted
        # 記錄為需要人工確認的異常付款
        if locked_booking["status"] != "accepted":

            cursor.execute(
                """
                UPDATE payments
                SET
                    status = 'refund_required',
                    ecpay_trade_no = %s,
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                AND status IN ('pending', 'superseded')
                """,
                (
                    ecpay_trade_no,
                    payment_record["id"]
                )
            )

            if cursor.rowcount != 1:
                return reply("0|UpdateFailed")

            connection.commit()

            logging.error(
                "ECPay payment requires review: "
                "booking_id=%s, payment_id=%s, booking_status=%s",
                payment_record["booking_id"],
                payment_record["id"],
                locked_booking["status"]
            )

            return reply("1|OK", 200)

        # 16-2. 正常付款成功
        cursor.execute(
            """
            UPDATE payments
            SET
                status = 'paid',
                ecpay_trade_no = %s,
                paid_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
              AND status IN ('pending', 'superseded')
            """,
            (
                ecpay_trade_no,
                payment_record["id"]
            )
        )


        if cursor.rowcount != 1:
            return reply("0|UpdateFailed")

        # 課程提醒：付款成功後通知老師
        # teachers.id 與 users.id 不同，必須先取得老師真正的會員 ID
        cursor.execute(
            """
            SELECT user_id
            FROM teachers
            WHERE id = %s
            """,
            (locked_booking["teacher_id"],)
        )

        teacher_record = cursor.fetchone()

        if teacher_record is None:
            raise HTTPException(
                status_code=500,
                detail="找不到課程對應的老師會員"
            )

        create_course_notification(
            cursor=cursor,
            user_id=teacher_record["user_id"],
            booking_id=payment_record["booking_id"],
            event_type="payment_paid"
        )

        # 17. 同時提交付款狀態與課程提醒
        connection.commit()

        logging.info(
            "綠界付款成功，訂單：%s，交易編號：%s",
            merchant_trade_no,
            ecpay_trade_no
        )

        return reply("1|OK", 200)

    except mysql.connector.Error:
        logging.exception(
            "綠界付款通知資料庫操作失敗：%s",
            merchant_trade_no
        )

        return reply("0|DatabaseError", 500)

    finally:
        if connection is not None and connection.is_connected():
            # 未提交的交易在離開函式時回滾
            # 已 commit 的交易不會被撤銷
            try:
                connection.rollback()
            except mysql.connector.Error:
                logging.exception("付款通知交易回滾失敗")

        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 綠界 Sandbox 訂單查詢
# GET /api/payments/{payment_id}/ecpay-status
@app.get("/api/payments/{payment_id}/ecpay-status", tags=["09｜第三方付款 Payments"])
def get_ecpay_payment_status(
    payment_id: int,
    user_id: int = Depends(get_current_user_id)
):
    # 僅允許 Sandbox 查詢
    if ECPAY_ENV != "stage":
        raise HTTPException(
            status_code=403,
            detail="此查詢 API 僅供 Sandbox 測試"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 查詢付款紀錄及預約學生
        cursor.execute(
            """
            SELECT
                p.id,
                p.booking_id,
                p.merchant_trade_no,
                p.amount,
                p.status,
                b.student_id
            FROM payments AS p
            JOIN bookings AS b ON b.id = p.booking_id
            WHERE p.id = %s
            """,
            (payment_id,)
        )

        payment_record = cursor.fetchone()

        if payment_record is None:
            raise HTTPException(
                status_code=404,
                detail="找不到付款紀錄"
            )

        if payment_record["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="無權查詢此付款紀錄"
            )

        # 主動向綠界查詢交易狀態
        result = query_ecpay_trade_info(
            payment_record["merchant_trade_no"]
        )

        # 驗證查詢結果金額
        trade_amount = result.get("TradeAmt", "")

        if (
            not trade_amount.isascii()
            or not trade_amount.isdecimal()
            or int(trade_amount) != int(payment_record["amount"])
        ):
            raise HTTPException(
                status_code=502,
                detail="綠界查詢結果金額不一致"
            )

        # 僅回傳必要資訊，不公開完整綠界回應
        return {
            "payment_id": payment_record["id"],
            "booking_id": payment_record["booking_id"],
            "merchant_trade_no": payment_record["merchant_trade_no"],
            "database_status": payment_record["status"],
            "ecpay_rtn_code": result.get("TradeStatus"),
            "ecpay_rtn_msg": result.get("TradeStatusDesc"),
            "ecpay_trade_no": result.get("TradeNo"),
            "trade_amount": int(trade_amount),
            "payment_date": result.get("PaymentDate")
        }

    except HTTPException:
        raise

    except (requests.RequestException, ValueError):
        logging.exception("綠界訂單查詢失敗")

        raise HTTPException(
            status_code=502,
            detail="無法驗證綠界交易結果"
        )

    except mysql.connector.Error:
        logging.exception("查詢付款資料失敗")

        raise HTTPException(
            status_code=500,
            detail="查詢付款資料失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 綠界 Sandbox 付款狀態同步
# POST /api/payments/{payment_id}/sync
# 目前僅允許同步測試付款 ID = 8
@app.post("/api/payments/{payment_id}/sync", tags=["09｜第三方付款 Payments"])
def sync_ecpay_payment(
    payment_id: int,
    user_id: int = Depends(get_current_user_id)
):
    if ECPAY_ENV != "stage" or payment_id != 8:
        raise HTTPException(
            status_code=403,
            detail="目前僅允許同步 Sandbox 測試付款 ID = 8"
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. 先確認付款紀錄及學生權限
        cursor.execute(
            """
            SELECT
                p.id,
                p.booking_id,
                p.merchant_trade_no,
                p.amount,
                b.student_id
            FROM payments AS p
            JOIN bookings AS b ON b.id = p.booking_id
            WHERE p.id = %s
            """,
            (payment_id,)
        )

        initial_payment = cursor.fetchone()

        if initial_payment is None:
            raise HTTPException(
                status_code=404,
                detail="找不到付款紀錄"
            )

        if initial_payment["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="無權同步此付款紀錄"
            )

        # 結束第一次唯讀交易，避免後續讀到舊快照
        connection.rollback()

        # 2. 向綠界重新查詢付款結果
        result = query_ecpay_trade_info(
            initial_payment["merchant_trade_no"]
        )

        trade_amount = str(result.get("TradeAmt", ""))
        trade_no = str(result.get("TradeNo", "")).strip()
        trade_status = str(result.get("TradeStatus", "")).strip()

        if trade_status != "1":
            raise HTTPException(
                status_code=409,
                detail="綠界尚未確認付款成功"
            )

        if (
            not trade_amount.isascii()
            or not trade_amount.isdecimal()
            or int(trade_amount) != int(initial_payment["amount"])
        ):
            raise HTTPException(
                status_code=502,
                detail="綠界付款金額不一致"
            )

        if (
            not trade_no
            or len(trade_no) > 30
            or not trade_no.isascii()
            or not trade_no.isalnum()
        ):
            raise HTTPException(
                status_code=502,
                detail="綠界交易編號格式錯誤"
            )

        # 3. 開始資料庫交易
        connection.start_transaction()

        # 固定鎖定順序：bookings -> payments
        cursor.execute(
            """
            SELECT
                id,
                student_id,
                teacher_id,
                status,
                total_amount
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (initial_payment["booking_id"],)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise HTTPException(
                status_code=404,
                detail="找不到預約紀錄"
            )

        if booking["student_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="無權同步此付款紀錄"
            )

        if booking["status"] != "accepted":
            raise HTTPException(
                status_code=409,
                detail="預約狀態不允許付款同步"
            )

        cursor.execute(
            """
            SELECT
                id,
                booking_id,
                merchant_trade_no,
                amount,
                status,
                ecpay_trade_no
            FROM payments
            WHERE id = %s
            FOR UPDATE
            """,
            (payment_id,)
        )

        payment = cursor.fetchone()

        if payment is None:
            raise HTTPException(
                status_code=404,
                detail="找不到付款紀錄"
            )

        # 4. 重新確認鎖定後的資料
        if (
            payment["booking_id"] != booking["id"]
            or payment["merchant_trade_no"]
                != initial_payment["merchant_trade_no"]
            or int(payment["amount"]) != int(trade_amount)
            or Decimal(str(booking["total_amount"]))
                != Decimal(trade_amount)
        ):
            raise HTTPException(
                status_code=409,
                detail="付款資料與預約資料不一致"
            )

        # 5. 檢查綠界交易編號是否被其他付款紀錄使用
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE ecpay_trade_no = %s
              AND id != %s
            LIMIT 1
            """,
            (trade_no, payment_id)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="綠界交易編號已被其他訂單使用"
            )

        # 6. 檢查同一堂課是否有其他已付款訂單
        cursor.execute(
            """
            SELECT id
            FROM payments
            WHERE booking_id = %s
              AND status = 'paid'
              AND id != %s
            LIMIT 1
            """,
            (booking["id"], payment_id)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="此預約已有其他付款成功紀錄"
            )

        # 7. 重複同步時直接回傳成功
        if payment["status"] == "paid":
            if payment["ecpay_trade_no"] != trade_no:
                raise HTTPException(
                    status_code=409,
                    detail="已付款紀錄的交易編號不一致"
                )

            connection.commit()

            return {
                "message": "此筆付款已同步，無須重複更新",
                "payment_id": payment_id,
                "status": "paid",
                "ecpay_trade_no": trade_no
            }

        if payment["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="付款狀態不允許同步"
            )

        if (
            payment["ecpay_trade_no"] is not None
            and payment["ecpay_trade_no"] != trade_no
        ):
            raise HTTPException(
                status_code=409,
                detail="付款交易編號不一致"
            )

        # 8. 更新付款狀態
        cursor.execute(
            """
            UPDATE payments
            SET
                status = 'paid',
                ecpay_trade_no = %s,
                paid_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
              AND status = 'pending'
            """,
            (trade_no, payment_id)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="付款狀態更新失敗"
            )

        # 課程提醒：付款同步成功後通知老師
        cursor.execute(
            """
            SELECT user_id
            FROM teachers
            WHERE id = %s
            """,
            (booking["teacher_id"],)
        )

        teacher_record = cursor.fetchone()

        if teacher_record is None:
            raise HTTPException(
                status_code=500,
                detail="找不到課程對應的老師會員"
            )

        create_course_notification(
            cursor=cursor,
            user_id=teacher_record["user_id"],
            booking_id=booking["id"],
            event_type="payment_paid"
        )

        # 付款狀態與課程提醒一起提交
        connection.commit()

        return {
            "message": "綠界付款狀態同步成功",
            "payment_id": payment_id,
            "booking_id": booking["id"],
            "status": "paid",
            "ecpay_trade_no": trade_no
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except (requests.RequestException, ValueError):
        if connection is not None:
            connection.rollback()

        logging.exception("綠界付款同步驗證失敗")

        raise HTTPException(
            status_code=502,
            detail="無法驗證綠界付款結果"
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("綠界付款同步資料庫操作失敗")

        raise HTTPException(
            status_code=500,
            detail="付款狀態同步失敗"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 課程提醒
# GET /api/course-notifications/unread
# 查詢目前會員是否有未讀課程提醒
@app.get("/api/course-notifications/unread", tags=["10｜課程提醒 Course Notifications"])
def get_unread_course_notifications(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM course_notifications
                WHERE user_id = %s
                  AND is_read = FALSE
            ) AS has_unread
            """,
            (user_id,)
        )

        result = cursor.fetchone()

        return {
            "has_unread": bool(
                result["has_unread"] if result else False
            )
        }

    except mysql.connector.Error:
        logging.exception("查詢課程未讀提醒失敗")

        raise HTTPException(
            status_code=500,
            detail="無法取得課程提醒狀態"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 課程提醒
# POST /api/course-notifications/read
# 將目前會員的課程提醒標記為已讀

@app.post("/api/course-notifications/read", tags=["10｜課程提醒 Course Notifications"])
def mark_course_notifications_read(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE course_notifications
            SET is_read = TRUE
            WHERE user_id = %s
              AND is_read = FALSE
            """,
            (user_id,)
        )

        updated_count = cursor.rowcount
        connection.commit()

        return {
            "success": True,
            "updated_count": updated_count,
            "has_unread": False
        }

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("標記課程提醒已讀失敗")

        raise HTTPException(
            status_code=500,
            detail="無法更新課程提醒狀態"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 評價通知中心
# GET /api/review-notifications
# 查詢目前登入會員的評價通知
@app.get("/api/review-notifications", tags=["11｜評價通知 Review Notifications"])
def get_review_notifications(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                rn.id,
                rn.booking_id,
                rn.review_id,
                b.teacher_id,
                rn.event_type,
                rn.is_read,
                rn.created_at
            FROM review_notifications AS rn
            INNER JOIN bookings AS b
                ON b.id = rn.booking_id
            WHERE rn.user_id = %s
            ORDER BY rn.created_at DESC, rn.id DESC
            LIMIT 50
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        notifications = []

        for row in rows:
            notifications.append({
                "id": row["id"],
                "booking_id": row["booking_id"],
                "review_id": row["review_id"],
                "teacher_id": row["teacher_id"],
                "event_type": row["event_type"],
                "is_read": bool(row["is_read"]),
                "created_at": (
                    row["created_at"].isoformat()
                    if row["created_at"]
                    else None
                )
            })

        return {
            "notifications": notifications,
            "total": len(notifications)
        }

    except mysql.connector.Error:
        logging.exception("查詢評價通知失敗")

        raise HTTPException(
            status_code=500,
            detail="無法取得評價通知"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 評價通知中心：未讀狀態
# GET /api/review-notifications/unread
@app.get(
    "/api/review-notifications/unread",
    tags=["11｜評價通知 Review Notifications"]
)
def get_unread_review_notifications(
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM review_notifications
                WHERE user_id = %s
                  AND is_read = FALSE
            ) AS has_unread
            """,
            (user_id,)
        )

        result = cursor.fetchone()

        return {
            "has_unread": bool(
                result["has_unread"] if result else False
            )
        }

    except mysql.connector.Error:
        logging.exception("查詢評價未讀通知失敗")

        raise HTTPException(
            status_code=500,
            detail="無法取得評價通知狀態"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# ==============================
# 評價通知中心：標記單筆通知為已讀
# POST /api/review-notifications/{notification_id}/read
@app.post(
    "/api/review-notifications/{notification_id}/read",
    tags=["11｜評價通知 Review Notifications"]
)
def mark_review_notification_read(
    notification_id: int,
    user_id: int = Depends(get_current_user_id)
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 只能修改目前登入會員自己的通知
        cursor.execute(
            """
            UPDATE review_notifications
            SET is_read = TRUE
            WHERE id = %s
              AND user_id = %s
              AND is_read = FALSE
            """,
            (notification_id, user_id)
        )

        updated_count = cursor.rowcount
        connection.commit()

        return {
            "success": True,
            "updated_count": updated_count
        }

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        logging.exception("標記評價通知已讀失敗")

        raise HTTPException(
            status_code=500,
            detail="無法更新評價通知狀態"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
