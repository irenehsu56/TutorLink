# ==============================
# AWS S3 連線設定

import os
import uuid
from botocore.exceptions import ClientError

import boto3
from dotenv import load_dotenv
from pathlib import Path

# ==============================
# 讀取專案根目錄的 .env

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# ==============================
# AWS S3 環境變數

AWS_REGION = os.getenv("AWS_REGION", "ap-east-2")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

# ==============================
# 建立 AWS S3 Client

# 指定 S3 Bucket 所在區域
# 避免產生 Presigned URL 時使用錯誤的 Endpoint
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com"
)

# ==============================
# 測試 S3 Bucket 是否可連線

def test_s3_connection():
    """
    測試能否透過 S3 上傳、讀取與刪除測試檔案。
    """

    if not AWS_S3_BUCKET:
        raise ValueError("尚未設定 AWS_S3_BUCKET")

    test_key = "_connection-test.txt"

    try:
        # 上傳測試檔案
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=test_key,
            Body=b"TutorLink S3 connection test"
        )

        # 讀取測試檔案
        response = s3_client.get_object(
            Bucket=AWS_S3_BUCKET,
            Key=test_key
        )
        response["Body"].read()

        # 刪除測試檔案
        s3_client.delete_object(
            Bucket=AWS_S3_BUCKET,
            Key=test_key
        )

        return True

    except Exception:
        # 保留原始錯誤，方便本機除錯
        raise

# ==============================
# 上傳老師頭貼至 AWS S3

def upload_teacher_photo(file, content_type: str) -> str:
    """
    將老師頭貼上傳至 AWS S3。

    參數：
        file：照片的二進位檔案物件
        content_type：照片的 MIME 類型

    回傳：
        photo_key：S3 物件的儲存路徑
    """

    # 確認已設定 S3 Bucket
    if not AWS_S3_BUCKET:
        raise ValueError("尚未設定 AWS_S3_BUCKET")

    # 依照圖片類型決定副檔名
    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp"
    }

    if content_type not in allowed_types:
        raise ValueError("只允許上傳 JPG、PNG 或 WebP 圖片")

    # 產生唯一的照片檔案名稱
    extension = allowed_types[content_type]
    filename = f"{uuid.uuid4().hex}{extension}"

    # S3 儲存路徑
    photo_key = f"teachers/photos/{filename}"

    try:
        # 上傳照片至 S3
        s3_client.upload_fileobj(
            Fileobj=file,
            Bucket=AWS_S3_BUCKET,
            Key=photo_key,
            ExtraArgs={
                "ContentType": content_type
            }
        )

        return photo_key

    except ClientError:
        # 保留 AWS 原始錯誤供後端記錄
        raise

# ==============================
# 刪除 AWS S3 上的老師頭貼

def delete_teacher_photo(photo_key: str) -> None:
    """
    刪除 AWS S3 中指定的老師頭貼。

    參數：
        photo_key：老師頭貼在 S3 的物件路徑
    """

    # 沒有頭貼路徑，不需要刪除
    if not photo_key:
        return

    # 確認已設定 S3 Bucket
    if not AWS_S3_BUCKET:
        raise ValueError("尚未設定 AWS_S3_BUCKET")

    # 避免刪除老師頭貼資料夾以外的物件
    if (
        not photo_key.startswith("teachers/photos/")
        or photo_key == "teachers/photos/"
    ):
        raise ValueError("無效的老師頭貼路徑")

    # 刪除指定的 S3 物件
    s3_client.delete_object(
        Bucket=AWS_S3_BUCKET,
        Key=photo_key
    )

# ==============================
# 產生老師頭貼的暫時讀取網址

def get_teacher_photo_url(photo_key: str) -> str:

    # 如果沒有照片路徑，回傳空字串
    if not photo_key:
        return ""

    # 產生 AWS S3 預先簽署網址
    # 即使 Bucket 是私人存取，也能透過此網址暫時讀取圖片
    photo_url = s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": AWS_S3_BUCKET,
            "Key": photo_key
        },
        ExpiresIn=3600  # 網址有效期限：1 小時
    )

    return photo_url