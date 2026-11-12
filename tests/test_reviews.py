# ==============================
# TutorLink｜學生課後評價自動化測試
# 使用 pytest + Mock 資料庫
# 不連接真正的 MySQL，不修改評價紀錄
# 執行方式：python -m pytest tests/test_reviews.py -v

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# ==============================
# 01｜未完成課程禁止發表評價
def test_uncompleted_booking_cannot_create_review(monkeypatch):
    """
    測試學生不能評價尚未完成的課程。

    模擬條件：
    - 學生 ID = 7
    - 預約 ID = 13
    - 預約狀態 = accepted
    - completed_at = None

    預期：
    1. API 回傳 HTTP 409
    2. 不新增評價
    3. 資料庫交易回滾
    """

    import main

    # 建立假的 MySQL 連線與 Cursor
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬尚未完成的課程
    cursor.fetchone.return_value = {
        "id": 13,
        "student_id": 7,
        "teacher_id": 9,
        "status": "accepted",
        "completed_at": None
    }

    # 使用 Mock 取代真正的資料庫連線
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立測試評價內容
    review = main.ReviewCreate(
        booking_id=13,
        content="測試未完成課程是否可以評價"
    )

    # 呼叫真正的新增評價函式
    with pytest.raises(HTTPException) as exc_info:
        main.create_review(
            review=review,
            user_id=7
        )

    # 確認 API 拒絕新增評價
    assert exc_info.value.status_code == 409

    assert "尚未確認完成課程" in str(
        exc_info.value.detail
    )

    # 確認沒有執行 INSERT
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認沒有提交交易
    connection.commit.assert_not_called()

    # 確認異常時執行 rollback
    connection.rollback.assert_called_once()

# ==============================
# 02｜學生不能修改其他學生的評價
def test_student_cannot_edit_other_student_review(monkeypatch):
    """
    測試學生不能修改其他學生發表的評價。

    模擬條件：
    - 評價 ID = 100
    - 原評價學生 ID = 7
    - 目前登入學生 ID = 8

    預期：
    1. 回傳 HTTP 403
    2. 不執行 UPDATE reviews
    3. 不提交資料庫交易
    4. 執行 rollback
    """

    import main

    # 建立假的 MySQL 連線
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬資料庫查到的原始評價
    cursor.fetchone.return_value = {
        "id": 100,
        "student_id": 7,
        "teacher_id": 9,
        "booking_id": 25
    }

    # 阻止連接真正的 MySQL
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 模擬學生 8 嘗試修改學生 7 的評價
    review = main.ReviewUpdate(
        content="嘗試修改其他學生的評價"
    )

    # 呼叫真正的修改評價函式
    with pytest.raises(HTTPException) as exc_info:
        main.update_review(
            review_id=100,
            review=review,
            user_id=8
        )

    # 確認 API 拒絕修改
    assert exc_info.value.status_code == 403
    assert "只能修改自己發表的評價" in str(
        exc_info.value.detail
    )

    # 確認沒有執行 UPDATE
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE reviews" in call.args[0]
    ]

    assert len(update_calls) == 0

    # 不應提交任何修改
    connection.commit.assert_not_called()

    # 權限驗證失敗應回滾交易
    connection.rollback.assert_called_once()

# ==============================
# 03｜老師不能修改其他老師的評價回覆
def test_teacher_cannot_edit_other_teacher_reply(monkeypatch):
    """
    測試老師不能修改其他老師收到的學生評價回覆。

    模擬條件：
    - 評價 ID = 100
    - 評價所屬老師的會員 ID = 6
    - 目前登入的會員 ID = 8
    - 原本已有老師回覆

    預期：
    1. 回傳 HTTP 403
    2. 不修改評價回覆
    3. 不提交資料庫交易
    4. 執行 rollback
    """

    import main

    # 建立假的 MySQL 連線
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬評價與所屬老師的資料
    cursor.fetchone.return_value = {
        "id": 100,
        "teacher_id": 9,
        "teacher_user_id": 6,
        "teacher_reply": "原本老師的回覆",
        "teacher_replied_at": None,
        "teacher_reply_edited_at": None
    }

    # 使用 Mock 取代真正的 MySQL 連線
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 模擬其他老師嘗試修改回覆
    reply = main.ReviewReplyCreate(
        content="嘗試修改其他老師的回覆"
    )

    # 呼叫真正的老師回覆 API
    with pytest.raises(HTTPException) as exc_info:
        main.reply_to_review(
            review_id=100,
            reply=reply,
            user_id=8
        )

    # 確認權限不足
    assert exc_info.value.status_code == 403

    assert "只有該課程的老師可以回覆或修改回覆" in str(
        exc_info.value.detail
    )

    # 確認沒有執行 UPDATE reviews
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE reviews" in call.args[0]
    ]

    assert len(update_calls) == 0

    # 不應提交修改
    connection.commit.assert_not_called()

    # 權限驗證失敗時應回滾
    connection.rollback.assert_called_once()

# ==============================
# 04｜已完成課程的學生可以新增評價
def test_completed_booking_can_create_review(monkeypatch):
    """
    測試符合資格的學生可以成功發表評價。

    模擬條件：
    - 學生 ID = 7
    - 預約 ID = 26
    - 老師 ID = 11
    - 預約狀態 = accepted
    - 老師已確認課程完成
    - 學生尚未評價過該老師

    預期：
    1. 成功執行 INSERT INTO reviews
    2. 評價歸屬正確的學生與老師
    3. 資料庫交易成功提交
    """

    import main
    from datetime import datetime

    # 建立 Mock 資料庫
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬依序查詢到的資料
    cursor.fetchone.side_effect = [
        {
            "id": 26,
            "student_id": 7,
            "teacher_id": 11,
            "status": "accepted",
            "completed_at": datetime(2026, 11, 10, 17, 2, 24)
        },
        None  # 尚未評價過這位老師
    ]

    # 模擬新增評價後產生的 ID
    cursor.lastrowid = 200

    # 替換真正的 MySQL 連線
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立評價資料
    review = main.ReviewCreate(
        booking_id=26,
        content="老師教學認真，講解清楚"
    )

    # 呼叫新增評價 API
    response = main.create_review(
        review=review,
        user_id=7
    )

    # 確認成功執行新增評價 SQL
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 1

    # 確認寫入的預約、學生、老師及評價內容
    insert_params = insert_calls[0].args[1]

    assert insert_params == (
        26,
        7,
        11,
        "老師教學認真，講解清楚"
    )

    # 確認資料庫交易提交
    connection.commit.assert_called_once()

    # 確認沒有回滾交易
    connection.rollback.assert_not_called()

    # 確認 API 有正常回傳結果
    assert response is not None

# ==============================
# 05｜同一位學生不能重複評價同一位老師
def test_student_cannot_review_same_teacher_twice(monkeypatch):
    """
    測試同一位學生不能對同一位老師重複發表評價。

    模擬條件：
    - 學生 ID = 7
    - 老師 ID = 9
    - 學生已有一則評價（ID = 1）
    - 學生再次嘗試新增評價

    預期：
    1. API 拒絕新增第二則評價
    2. 不執行 INSERT INTO reviews
    3. 不提交資料庫交易
    """

    import main
    from datetime import datetime

    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬資料庫查詢結果
    cursor.fetchone.side_effect = [
        {
            "id": 25,
            "student_id": 7,
            "teacher_id": 9,
            "status": "accepted",
            "completed_at": datetime(2026, 11, 9, 14, 0, 21)
        },
        {
            "id": 1,
            "student_id": 7,
            "teacher_id": 9
        }
    ]

    # 使用 Mock 資料庫
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 嘗試新增第二則評價
    review = main.ReviewCreate(
        booking_id=25,
        content="第二次評價同一位老師"
    )

    # 預期後端拒絕新增
    with pytest.raises(HTTPException) as exc_info:
        main.create_review(
            review=review,
            user_id=7
        )

    # 確認回傳衝突狀態
    assert exc_info.value.status_code == 409

    # 確認沒有新增評價
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認沒有提交交易
    connection.commit.assert_not_called()

# ==============================
# 06｜學生可以編輯自己發表的評價
def test_student_can_edit_own_review(monkeypatch):
    """
    測試學生可以修改自己發表的評價。

    模擬條件：
    - 評價 ID = 100
    - 評價所屬學生 ID = 7
    - 目前登入學生 ID = 7

    預期：
    1. 成功更新原本的評價
    2. 不新增第二則評價
    3. 正確記錄修改時間
    4. 提交資料庫交易
    """

    import main

    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬學生自己的評價
    cursor.fetchone.return_value = {
        "id": 100,
        "student_id": 7,
        "teacher_id": 9,
        "booking_id": 25,
        "content": "原本的評價內容"
    }

    # 使用 Mock 資料庫
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立修改後的評價內容
    review = main.ReviewUpdate(
        content="老師講解清楚，課程內容很實用"
    )

    # 執行修改評價 API
    response = main.update_review(
        review_id=100,
        review=review,
        user_id=7
    )

    # 找出更新評價的 SQL
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE reviews" in call.args[0]
    ]

    # 應該只更新一次
    assert len(update_calls) == 1

    update_sql = update_calls[0].args[0]
    update_params = update_calls[0].args[1]

    # 確認有更新評價內容與編輯時間
    assert "content" in update_sql
    assert "review_edited_at" in update_sql

    # 確認新的評價內容有傳入 SQL
    assert "老師講解清楚，課程內容很實用" in update_params

    # 不應新增第二則評價
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認交易提交
    connection.commit.assert_called_once()

    # 不應發生 rollback
    connection.rollback.assert_not_called()

    # 確認 API 有正常回傳
    assert response is not None

# ==============================
# 07｜老師可以成功回覆自己的學生評價
def test_teacher_can_reply_to_own_review(monkeypatch):
    """
    測試老師可以首次回覆自己收到的學生評價。

    模擬條件：
    - 評價 ID = 100
    - 老師 ID = 9
    - 老師會員 ID = 6
    - 目前登入會員 ID = 6
    - 原本尚未有老師回覆

    預期：
    1. 成功更新老師回覆內容
    2. 記錄首次回覆時間
    3. 編輯時間維持 NULL
    4. 提交資料庫交易
    5. 不新增第二筆評價
    """

    import main

    # 建立 Mock 資料庫
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬老師自己收到的評價
    cursor.fetchone.return_value = {
        "id": 100,
        "teacher_id": 9,
        "teacher_user_id": 6,
        "teacher_reply": None,
        "teacher_replied_at": None,
        "teacher_reply_edited_at": None
    }

    # 阻止連接真實 MySQL
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立老師回覆內容
    reply = main.ReviewReplyCreate(
        content="謝謝你的評價，很高興能幫助你！"
    )

    # 呼叫真正的老師回覆函式
    response = main.reply_to_review(
        review_id=100,
        reply=reply,
        user_id=6
    )

    # 找出更新評價的 SQL
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE reviews" in call.args[0]
    ]

    # 應該只更新一次
    assert len(update_calls) == 1

    update_sql = update_calls[0].args[0]
    update_params = update_calls[0].args[1]

    # 確認有更新老師回覆
    assert "teacher_reply = %s" in update_sql

    # 首次回覆應記錄回覆時間
    assert "teacher_replied_at = NOW()" in update_sql

    # 首次回覆不應被標記為已編輯
    assert "teacher_reply_edited_at = NULL" in update_sql

    # 確認回覆內容及評價 ID 正確
    assert update_params == (
        "謝謝你的評價，很高興能幫助你！",
        100
    )

    # 不應新增其他評價
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認交易成功提交
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()

    # 確認 API 回傳內容
    assert response["message"] == "老師回覆成功"
    assert response["review_id"] == 100
    assert response["teacher_id"] == 9
    assert response["is_edited"] is False

# ==============================
# 08｜老師可以編輯自己的評價回覆
def test_teacher_can_edit_own_reply(monkeypatch):
    """
    測試老師可以修改自己先前發表的回覆。

    模擬條件：
    - 評價 ID = 100
    - 老師 ID = 9
    - 老師會員 ID = 6
    - 目前登入會員 ID = 6
    - 原本已有老師回覆

    預期：
    1. 成功更新回覆內容
    2. 保留首次回覆時間
    3. 更新回覆編輯時間
    4. 不新增評價紀錄
    5. 提交資料庫交易
    """

    import main
    from datetime import datetime

    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value = cursor
    connection.is_connected.return_value = True

    # 模擬老師先前已經回覆過的評價
    cursor.fetchone.return_value = {
        "id": 100,
        "teacher_id": 9,
        "teacher_user_id": 6,
        "teacher_reply": "謝謝你的評價！",
        "teacher_replied_at": datetime(
            2026, 11, 11, 10, 0, 0
        ),
        "teacher_reply_edited_at": None
    }

    # 使用 Mock 資料庫
    monkeypatch.setattr(
        main,
        "get_db_connection",
        lambda: connection
    )

    # 建立修改後的老師回覆
    reply = main.ReviewReplyCreate(
        content="謝謝你的支持，期待下次一起學習！"
    )

    # 執行老師回覆 API
    response = main.reply_to_review(
        review_id=100,
        reply=reply,
        user_id=6
    )

    # 找出 UPDATE reviews 的 SQL
    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE reviews" in call.args[0]
    ]

    # 只能更新一次
    assert len(update_calls) == 1

    update_sql = update_calls[0].args[0]
    update_params = update_calls[0].args[1]

    # 確認更新老師回覆內容
    assert "teacher_reply = %s" in update_sql

    # 修改回覆時應更新編輯時間
    assert "teacher_reply_edited_at = NOW()" in update_sql

    # 不應重新設定首次回覆時間
    assert "teacher_replied_at = NOW()" not in update_sql

    # 確認 SQL 參數正確
    assert update_params == (
        "謝謝你的支持，期待下次一起學習！",
        100
    )

    # 不應新增第二筆評價
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO reviews" in call.args[0]
    ]

    assert len(insert_calls) == 0

    # 確認資料庫交易成功提交
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()

    # 確認 API 回傳結果
    assert response["message"] == "老師回覆修改成功"
    assert response["review_id"] == 100
    assert response["teacher_id"] == 9
    assert response["is_edited"] is True
