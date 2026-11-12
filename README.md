# TutorLink｜家教媒合平台

TutorLink 是一個以 **Python FastAPI、MySQL 與原生 JavaScript** 開發的家教媒合平台，旨在提供學生與家教老師一個方便的線上媒合環境。

學生可以搜尋家教老師、查看老師詳細資料、收藏老師、站內私訊及預約課程；老師則可以管理個人教學資料、回覆訊息、處理課程預約，並在課程結束後與學生進行評價互動。

平台整合了會員管理、課程行事曆、第三方金流與通知功能，提供從尋找老師到完成課程的完整操作流程。

本專案為 **WeHelp 第三階段個人專案**。

**網站連結：** https://tutorlink.life

**GitHub Repository：** https://github.com/irenehsu56/TutorLink

---

## 使用技術

| 類別 | 技術 |
|---|---|
| Backend | Python、FastAPI |
| Frontend | HTML、CSS、JavaScript、Jinja2 |
| Database | MySQL（AWS RDS） |
| Authentication | JWT、Argon2 密碼雜湊 |
| File Storage | AWS S3 |
| Cloud Deployment | AWS EC2 |
| Web Server | Nginx |
| HTTPS | SSL/TLS |
| Payment | ECPay 綠界科技（Sandbox） |
| Testing | Pytest |
| Version Control | Git、GitHub |

---

## 已實作功能

### 1. 會員系統

- 會員註冊、登入及登出
- JWT 身分驗證與登入狀態管理
- 學生與家教老師身分管理
- 會員個人資料查看與姓名編輯
- 會員頭貼上傳與顯示
- 修改密碼及原密碼驗證
- 密碼使用 Argon2 雜湊儲存
- 會員帳號刪除及資料匿名化處理
- 登入與登出時同步更新會員介面

### 2. 家教老師管理

- 申請成為家教老師
- 建立、編輯及刪除老師資料
- 上傳老師個人頭貼
- 設定教學科目、年級、地區、收費及可授課時段
- 老師列表與條件搜尋
- 老師詳細介紹頁面
- 收藏及取消收藏老師
- 查看個人公開老師頁面

### 3. 站內私訊系統

- 學生與老師一對一私訊
- 對話列表及聊天紀錄
- 未讀訊息數量提示
- 聊天對象頭貼顯示
- 預約事件訊息卡片
- 依會員登入狀態顯示對應的聊天室內容

### 4. 課程預約系統

- 學生選擇老師可授課日期與時間
- 設定課程時長並計算預估費用
- 學生提出及取消預約
- 老師接受或拒絕預約
- 預約時間衝突檢查
- 支援連續開放時段的跨時段預約
- 預約狀態即時顯示
- 老師標記課程完成

### 5. 我的課程與個人行事曆

- 月曆形式查看課程預約
- 依日期查看課程資訊
- 顯示已確認、待確認、已取消及已拒絕等狀態
- 課程紀錄管理
- 查看課程付款與評價狀態
- 依會員身分顯示對應課程資訊

### 6. 第三方金流付款

- 串接 ECPay 綠界科技第三方金流
- 建立課程付款訂單
- 導向綠界付款頁面
- 接收並驗證付款結果通知
- 查詢及同步付款狀態
- 提供付款流程相關測試

**目前使用 ECPay Sandbox 測試環境，尚非正式信用卡收款服務。**

### 7. 課後評價系統

- 學生針對符合資格的已完成課程發表文字評價
- 不使用星等或分數評分
- 學生編輯自己的評價
- 老師回覆及編輯自己的回覆
- 評價與課程預約資料關聯
- 在老師詳細頁面展示學生評價及老師回覆
- 透過後端權限驗證限制非本人修改內容

### 8. 通知系統

- 站內未讀訊息提示
- 課程相關通知
- 評價相關通知
- 會員登入狀態與通知介面整合

---

## 系統部署

TutorLink 使用 AWS 雲端服務部署，主要架構如下：

- **AWS EC2：** 執行 FastAPI 後端應用程式
- **AWS RDS：** 儲存 MySQL 關聯式資料
- **AWS S3：** 儲存會員及老師頭貼
- **Nginx：** 提供反向代理服務
- **HTTPS：** 保護網站傳輸連線
- **自訂網域：** https://tutorlink.life

---

## 專案安裝

### 1. Clone Repository

```bash
git clone https://github.com/irenehsu56/TutorLink.git
cd TutorLink
```

### 2. 建立虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows 使用者可依使用的終端機啟動虛擬環境。

### 3. 安裝套件

```bash
pip install -r requirements.txt
```

### 4. 設定環境變數

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

依照實際開發環境填入以下設定：

- MySQL 資料庫連線資訊
- JWT Secret Key
- AWS S3 儲存設定
- ECPay Sandbox 測試商店資訊

`.env` 包含敏感資訊，不應提交至 GitHub。

AWS 憑證建議使用 IAM Role 等安全的憑證管理方式提供。

### 5. 準備 MySQL 資料庫

啟動前需先建立對應的 MySQL 資料庫及資料表。

專案包含部分資料庫相關 SQL，但目前尚未提供完整的一鍵初始化腳本。

### 6. 啟動開發伺服器

```bash
uvicorn main:app --reload
```

啟動後可透過以下網址開啟網站：

http://127.0.0.1:8000

FastAPI API 文件：

http://127.0.0.1:8000/docs

---

## 測試

專案使用 Pytest 進行部分後端功能測試，包含：

- 綠界付款結果通知驗證
- 課後評價與老師回覆相關功能

在設定好必要的測試環境與相依服務後，可執行：

```bash
python -m pytest tests/
```

---

## 開發者

本專案由個人獨立規劃與開發，作為 WeHelp 第三階段作品。

**GitHub：** [irenehsu56](https://github.com/irenehsu56)