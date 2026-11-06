
# TutorLink｜家教媒合平台

TutorLink 是一個使用 FastAPI、MySQL 與原生 JavaScript 開發的家教媒合平台，目標是讓學生更方便地尋找適合的家教老師，並透過站內私訊及預約系統安排課程。

本專案為 WeHelp 第三階段個人作品。

## 使用技術

- Backend：Python、FastAPI
- Frontend：HTML、CSS、JavaScript、Jinja2
- Database：MySQL（AWS RDS）
- Authentication：JWT
- File Storage：AWS S3
- Deployment：AWS EC2

## 已實作功能

### 1. 會員系統
- 會員註冊、登入及登出
- JWT 身分驗證
- 學生與老師身分管理
- 會員帳號刪除

### 2. 家教老師
- 老師資料建立、編輯及刪除
- 老師頭貼上傳
- 老師列表與條件搜尋
- 老師詳細介紹頁面
- 收藏及取消收藏老師

### 3. 站內私訊
- 學生與老師一對一私訊
- 未讀訊息提示
- 預約事件訊息卡片

### 4. 課程預約
- 學生提出課程預約
- 老師接受或拒絕預約
- 學生取消預約
- 預約時間衝突檢查
- 預約狀態顯示
- 個人行事曆

## 未來規劃

- 學生課後評價（不開放評分）＆ 老師回覆學生評價
- 第三方金流付款
- 會員系統優化，如個人資料編輯（含頭貼）、忘記密碼、重設密碼、修改密碼等
- 網頁優化，如聊天室加入頭貼、做 Footer 等

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

### 3. 安裝套件

```bash
pip install -r requirements.txt
```

### 4. 設定環境變數

複製 `.env.example` 為 `.env`，並填入 MySQL、JWT、AWS S3 等設定。

AWS 憑證請透過適當的憑證管理方式提供，例如 EC2 IAM Role。

### 5. 啟動開發伺服器

```bash
uvicorn main:app --reload
```

預設可透過 http://127.0.0.1:8000 開啟網站。

> 啟動前需準備對應的 MySQL 資料庫與資料表。本專案目前尚未提供完整的資料庫初始化腳本。

## 開發者

GitHub：[irenehsu56](https://github.com/irenehsu56)
