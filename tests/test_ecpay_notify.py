# TutorLink｜綠界 ECPay 付款通知自動化測試
# 測試工具：pytest + unittest.mock
# 使用 Mock 模擬 MySQL 與綠界通知，不會建立真正的綠界交易或修改 MySQL 付款紀錄。
# CheckMacValue 的計算已被 Mock 取代，測試通過不代表真實金流整合已完成驗收。
# 執行方式：python -m pytest tests/test_ecpay_notify.py -v

from unittest.mock import MagicMock

# ==============================
# 01｜確認 pytest 測試環境
def test_pytest_environment():
    """
    確認 pytest 可以正常執行測試函式。

    這是最基本的環境測試，
    不會呼叫 FastAPI、MySQL 或綠界。
    """
    assert True

# ==============================
# 02｜確認 FastAPI 可以安全匯入
def test_fastapi_import_without_database(monkeypatch):
    """
    測試匯入 main.py 時，FastAPI 是否可以正常初始化。

    使用 monkeypatch 暫時取代 MySQL 連線函式，
    如果測試期間嘗試透過 mysql.connector.connect()
    建立資料庫連線，就立即拋出錯誤。
    """

    import mysql.connector

    # 建立禁止連線的替代函式
    def block_database_connection(*args, **kwargs):
        raise AssertionError(
            "測試期間禁止連接 MySQL 資料庫"
        )

    # 暫時覆蓋 mysql.connector.connect()
    monkeypatch.setattr(
        mysql.connector,
        "connect",
        block_database_connection
    )

    # 匯入 TutorLink 的 FastAPI 應用程式
    import main

    # 確認 FastAPI 已成功建立
    assert main.app is not None

    # 確認載入的是 TutorLink API
    assert main.app.title == "TutorLink API"

# ==============================
# 03｜建立共用 Mock 資料庫
def create_mock_database():
    """
    建立測試專用的假資料庫連線與 Cursor。

    MagicMock 可以模擬：
    - connection.start_transaction()
    - connection.commit()
    - connection.rollback()
    - cursor.execute()
    - cursor.fetchone()
    - cursor.rowcount

    不需要真正連接 MySQL。
    """

    # 模擬 MySQL Connection
    mock_connection = MagicMock()

    # 模擬 MySQL Cursor
    mock_cursor = MagicMock()

    # 呼叫 connection.cursor() 時回傳假 Cursor
    mock_connection.cursor.return_value = mock_cursor

    # 模擬資料庫連線處於正常狀態
    mock_connection.is_connected.return_value = True

    return mock_connection, mock_cursor

def test_mock_database_environment():
    """
    確認 Mock 資料庫可以模擬基本交易流程。

    測試：
    1. 開始交易
    2. 執行 SQL
    3. 提交交易
    """

    connection, cursor = create_mock_database()

    # 模擬資料庫交易
    connection.start_transaction()
    cursor.execute("SELECT 1")
    connection.commit()

    # 確認每個操作都執行一次
    connection.start_transaction.assert_called_once()
    cursor.execute.assert_called_once_with("SELECT 1")
    connection.commit.assert_called_once()

# ==============================
# 04｜正常付款成功：pending → paid
def test_pending_payment_success(monkeypatch):
    """
    測試學生完成綠界付款後，
    TutorLink 是否正確更新付款狀態。

    模擬條件：
    - 預約狀態為 accepted
    - 付款狀態為 pending
    - 沒有其他已付款訂單
    - 綠界回傳 RtnCode = 1

    預期結果：
    - 更新 payments.status 為 paid
    - 提交資料庫交易
    - 回傳 HTTP 200 與 1|OK
    """

    import asyncio
    import main
    from starlette.responses import PlainTextResponse

    connection, cursor = create_mock_database()

    # 依照通知 API 執行 SQL 的順序，
    # 模擬每一次 cursor.fetchone() 的結果
    cursor.fetchone.side_effect = [
        {"booking_id": 999},               # 取得付款所屬預約
        {"id": 999, "status": "accepted"},   # 鎖定預約
        {
            "id": 999,
            "booking_id": 999,
            "merchant_trade_no": "TLTESTPAYMENT001",
            "amount": 300,
            "status": "pending",
            "ecpay_trade_no": None
        },
        None,  # 沒有其他付款使用相同綠界交易編號
        None   # 同一堂課沒有其他 paid 訂單
    ]

    # 模擬 UPDATE 成功更新一筆資料
    cursor.rowcount = 1

    # 將真正的資料庫連線替換成 Mock
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 模擬 CheckMacValue 計算結果
    # 這裡不測試真實的綠界簽章演算法
    monkeypatch.setattr(
        main,
        "generate_ecpay_check_mac_value",
        lambda data: "TEST_MAC"
    )

    # 模擬綠界付款成功通知
    notify_data = {
        "MerchantTradeNo": "TLTESTPAYMENT001",
        "MerchantID": main.ECPAY_MERCHANT_ID,
        "TradeAmt": "300",
        "RtnCode": "1",
        "TradeNo": "1234567890123456",
        "CheckMacValue": "TEST_MAC"
    }

    # 模擬 FastAPI Request 的 form() 方法
    class MockRequest:
        async def form(self):
            return notify_data

    # 執行真正的付款通知函式
    # asyncio.run() 用來執行 async def 函式
    response = asyncio.run(
        main.ecpay_payment_notify(MockRequest())
    )

    # 確認回傳的是純文字回應
    assert isinstance(response, PlainTextResponse)

    # 確認通知處理成功
    assert response.status_code == 200
    assert response.body == b"1|OK"

    # 確認資料庫交易已提交
    connection.commit.assert_called_once()

    # 從所有 SQL 操作中找出 UPDATE payments
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE payments" in call.args[0]
    ]

    # 應該只更新一次付款資料
    assert len(update_calls) == 1

    # 確認 SQL 將付款狀態更新為 paid
    assert "status = 'paid'" in update_calls[0].args[0]

# ==============================
# 05｜已付款訂單收到重複通知
def test_paid_payment_duplicate_notification(monkeypatch):
    """
    測試同一筆已付款訂單再次收到綠界成功通知。

    模擬條件：
    - 付款狀態已經是 paid
    - 綠界再次傳送相同 TradeNo
    - RtnCode = 1

    預期結果：
    - 回傳 1|OK
    - 不再次 UPDATE payments
    - 不建立新付款訂單

    這是在驗證付款通知的冪等性：
    相同通知重複執行，不應產生額外的付款異動。
    """

    import asyncio
    import main

    connection, cursor = create_mock_database()

    cursor.fetchone.side_effect = [
        {"booking_id": 999},
        {"id": 999, "status": "accepted"},
        {
            "id": 100,
            "booking_id": 999,
            "merchant_trade_no": "TLTESTPAYMENT002",
            "amount": 300,
            "status": "paid",
            "ecpay_trade_no": "1234567890123456"
        },
        None  # 沒有其他訂單使用相同 TradeNo
    ]

    # 使用 Mock 資料庫
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 模擬綠界簽章
    monkeypatch.setattr(
        main,
        "generate_ecpay_check_mac_value",
        lambda data: "TEST_MAC"
    )

    notify_data = {
        "MerchantTradeNo": "TLTESTPAYMENT002",
        "MerchantID": main.ECPAY_MERCHANT_ID,
        "TradeAmt": "300",
        "RtnCode": "1",
        "TradeNo": "1234567890123456",
        "CheckMacValue": "TEST_MAC"
    }

    class MockRequest:
        async def form(self):
            return notify_data

    response = asyncio.run(
        main.ecpay_payment_notify(MockRequest())
    )

    # 相同成功通知應正常回覆
    assert response.status_code == 200
    assert response.body == b"1|OK"

    # 確認沒有再次執行 UPDATE
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE payments" in call.args[0]
    ]

    assert len(update_calls) == 0

    # 確認沒有建立新付款訂單
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO payments" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認交易正常提交
    connection.commit.assert_called_once()

# ==============================
# 06｜舊訂單付款成功：superseded → refund_required
def test_superseded_payment_requires_refund(monkeypatch):
    """
    測試已被新付款訂單取代的舊訂單，
    又收到綠界付款成功通知。

    模擬條件：
    - 舊訂單狀態為 superseded
    - 同一堂課已有另一筆 paid 訂單
    - 舊訂單又收到 RtnCode = 1

    預期結果：
    - 舊訂單更新為 refund_required
    - 保存綠界交易編號
    - 不將舊訂單當成第二筆正常付款
    - 回傳 1|OK

    注意：
    refund_required 代表需要人工核對或退款，
    不代表系統已自動完成退款。
    """

    import asyncio
    import main

    connection, cursor = create_mock_database()

    cursor.fetchone.side_effect = [
        {"booking_id": 999},
        {"id": 999, "status": "accepted"},
        {
            "id": 101,
            "booking_id": 999,
            "merchant_trade_no": "TLTESTPAYMENT003",
            "amount": 300,
            "status": "superseded",
            "ecpay_trade_no": None
        },
        None,        # 沒有重複的綠界交易編號
        {"id": 102}  # 同一堂課已有另一筆 paid 訂單
    ]

    # 模擬資料庫更新成功
    cursor.rowcount = 1

    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    monkeypatch.setattr(
        main,
        "generate_ecpay_check_mac_value",
        lambda data: "TEST_MAC"
    )

    notify_data = {
        "MerchantTradeNo": "TLTESTPAYMENT003",
        "MerchantID": main.ECPAY_MERCHANT_ID,
        "TradeAmt": "300",
        "RtnCode": "1",
        "TradeNo": "1234567890123457",
        "CheckMacValue": "TEST_MAC"
    }

    class MockRequest:
        async def form(self):
            return notify_data

    response = asyncio.run(
        main.ecpay_payment_notify(MockRequest())
    )

    # 綠界通知應正常完成處理
    assert response.status_code == 200
    assert response.body == b"1|OK"

    # 取得所有付款 UPDATE 操作
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE payments" in call.args[0]
    ]

    # 異常付款應更新一次
    assert len(update_calls) == 1

    update_sql = update_calls[0].args[0]
    update_params = update_calls[0].args[1]

    # 確認更新為需要退款的狀態
    assert "status = 'refund_required'" in update_sql

    # 確認保存綠界交易編號
    assert update_params[0] == "1234567890123457"

    # 確認只更新舊付款 ID 101
    assert update_params[1] == 101

    # 確認資料庫交易提交
    connection.commit.assert_called_once()

# ==============================
# 07｜refund_required 收到重複成功通知
def test_refund_required_duplicate_notification(monkeypatch):
    """
    測試已經標記為 refund_required 的付款，
    再次收到相同的綠界成功通知。

    預期結果：
    - 回傳 1|OK
    - 不重複 UPDATE
    - 不建立新付款訂單
    - 保留原本的異常付款狀態
    """

    import asyncio
    import main

    connection, cursor = create_mock_database()

    cursor.fetchone.side_effect = [
        {"booking_id": 999},
        {"id": 999, "status": "accepted"},
        {
            "id": 101,
            "booking_id": 999,
            "merchant_trade_no": "TLTESTPAYMENT004",
            "amount": 300,
            "status": "refund_required",
            "ecpay_trade_no": "1234567890123458"
        },
        None
    ]

    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    monkeypatch.setattr(
        main,
        "generate_ecpay_check_mac_value",
        lambda data: "TEST_MAC"
    )

    notify_data = {
        "MerchantTradeNo": "TLTESTPAYMENT004",
        "MerchantID": main.ECPAY_MERCHANT_ID,
        "TradeAmt": "300",
        "RtnCode": "1",
        "TradeNo": "1234567890123458",
        "CheckMacValue": "TEST_MAC"
    }

    class MockRequest:
        async def form(self):
            return notify_data

    response = asyncio.run(
        main.ecpay_payment_notify(MockRequest())
    )

    # 重複通知應正常回覆
    assert response.status_code == 200
    assert response.body == b"1|OK"

    # 不應再次更新付款紀錄
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE payments" in call.args[0]
    ]

    assert len(update_calls) == 0

    # 不應建立新付款訂單
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO payments" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認資料庫交易正常提交
    connection.commit.assert_called_once()

# ==============================
# 08｜課程已取消，但綠界才通知付款成功
def test_cancelled_booking_payment_requires_refund(monkeypatch):
    """
    測試課程已取消後，才收到綠界付款成功通知。

    模擬條件：
    - bookings.status = cancelled
    - payments.status = pending
    - 綠界回傳 RtnCode = 1
    - 同一堂課沒有其他 paid 訂單

    預期結果：
    - 不視為正常課程付款
    - 更新付款狀態為 refund_required
    - 保存綠界交易編號
    - 回傳 1|OK

    避免付款成功卻因課程取消而漏記交易。
    """

    import asyncio
    import main

    connection, cursor = create_mock_database()

    cursor.fetchone.side_effect = [
        {"booking_id": 999},
        {"id": 999, "status": "cancelled"},
        {
            "id": 103,
            "booking_id": 999,
            "merchant_trade_no": "TLTESTPAYMENT005",
            "amount": 300,
            "status": "pending",
            "ecpay_trade_no": None
        },
        None,  # 沒有其他訂單使用相同 TradeNo
        None   # 沒有其他已付款訂單
    ]

    cursor.rowcount = 1

    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    monkeypatch.setattr(
        main,
        "generate_ecpay_check_mac_value",
        lambda data: "TEST_MAC"
    )

    notify_data = {
        "MerchantTradeNo": "TLTESTPAYMENT005",
        "MerchantID": main.ECPAY_MERCHANT_ID,
        "TradeAmt": "300",
        "RtnCode": "1",
        "TradeNo": "1234567890123459",
        "CheckMacValue": "TEST_MAC"
    }

    class MockRequest:
        async def form(self):
            return notify_data

    response = asyncio.run(
        main.ecpay_payment_notify(MockRequest())
    )

    # 確認付款通知正常回覆
    assert response.status_code == 200
    assert response.body == b"1|OK"

    # 找出付款狀態更新 SQL
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE payments" in call.args[0]
    ]

    # 應該只更新一筆付款資料
    assert len(update_calls) == 1

    update_sql = update_calls[0].args[0]
    update_params = update_calls[0].args[1]

    # 已取消課程的付款應標記為異常
    assert "status = 'refund_required'" in update_sql

    # 確認保存綠界交易編號
    assert update_params[0] == "1234567890123459"

    # 確認只更新指定付款 ID 103
    assert update_params[1] == 103

    # 確認資料庫交易提交
    connection.commit.assert_called_once()

# ==============================
# 09｜異常付款禁止再次建立付款訂單
def test_refund_required_blocks_new_payment(monkeypatch):
    """
    測試課程存在 refund_required 紀錄時，
    後端是否禁止學生再次建立付款訂單。

    預期：
    1. 回傳 HTTP 409
    2. 不建立新付款紀錄
    3. 不產生新的綠界訂單
    """
    import main
    from fastapi import HTTPException

    connection, cursor = create_mock_database()

    # 模擬 SQL 查詢結果：
    # 1. 學生自己的已接受預約
    # 2. 沒有正常 paid 紀錄
    # 3. 存在 refund_required 紀錄
    cursor.fetchone.side_effect = [
        {
            "id": 999,
            "student_id": 7,
            "status": "accepted",
            "total_amount": 300
        },
        None,
        {"id": 103}
    ]

    # 使用假資料庫，避免連接真實 MySQL
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立測試用付款請求
    payment = main.PaymentCreate(booking_id=999)

    # 呼叫真正的付款建立 API
    try:
        main.create_payment(
            payment=payment,
            user_id=7
        )

    except HTTPException as exc:
        # 應禁止再次付款
        assert exc.status_code == 409
        assert "異常付款" in str(exc.detail)

    else:
        raise AssertionError(
            "存在 refund_required 時，不應允許建立付款訂單"
        )

    # 確認沒有建立新的付款資料
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO payments" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認程式沒有查詢後續 pending 訂單
    pending_queries = [
        call
        for call in cursor.execute.call_args_list
        if "status = 'pending'" in call.args[0]
    ]

    assert len(pending_queries) == 0
