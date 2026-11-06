if (window.lucide) {lucide.createIcons();}

// ==============================
// 我的訊息｜對話列表
// ==============================
// 取得對話列表容器
const conversationsList = document.getElementById("conversations-list");

// 取得聊天主要版型與返回按鈕
const messagesLayout = document.querySelector(".messages-layout");
const chatBackButton = document.getElementById("chat-back-button");

// 記錄目前選取的對話 ID
let activeConversationId = null;

// 記錄目前正在傳送訊息的會員 Token
let sendingMessageToken = null;

// 記錄聊天紀錄請求版本，避免舊請求覆蓋新結果
let chatMessagesRequestId = 0;

// 記錄對話列表請求版本，避免舊請求覆蓋新結果
let conversationsRequestId = 0;

// ==============================
// 清除目前會員的聊天畫面
// ==============================
function clearMessagesPage() {

    // 清除目前選取的對話
    activeConversationId = null;

    // 會員切換時重設傳送狀態
    sendingMessageToken = null;

    // 讓上一位會員尚未完成的聊天紀錄請求失效
    chatMessagesRequestId++;

    // 讓上一位會員尚未完成的對話列表請求失效
    conversationsRequestId++;

    // 清空對話列表
    if (conversationsList) {
        conversationsList.replaceChildren();
    }

    // 手機版返回對話列表
    if (messagesLayout) {
        messagesLayout.classList.remove("chat-open");
    }

    // 取得聊天區域元素
    const chatEmptyState = document.getElementById("chat-empty-state");
    const chatContent = document.getElementById("chat-content");
    const chatPartnerName = document.getElementById("chat-partner-name");
    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");

    // 恢復尚未選擇對話的畫面
    if (chatEmptyState) {
        chatEmptyState.hidden = false;
    }

    if (chatContent) {
        chatContent.hidden = true;
    }

    // 清除上一位會員的聊天資料
    if (chatPartnerName) {
        chatPartnerName.textContent = "";
    }

    if (chatMessages) {
        chatMessages.replaceChildren();
    }

    if (chatInput) {
        chatInput.value = "";
    }

    // 取得傳送訊息按鈕
    const sendButton = document.querySelector('#chat-form button[type="submit"]');

    // 會員切換時恢復按鈕狀態
    if (sendButton) {
        sendButton.disabled = false;
    }

}

// ==============================
// 格式化最後訊息時間
// ==============================
function formatConversationTime(dateString) {
    if (!dateString) return "";

    // MySQL DATETIME 若沒有時區，依網站使用的台灣時間解析
    const normalized = String(dateString).replace(" ", "T");
    // 資料庫時間為 UTC
    // 若沒有附帶時區資訊，補上 Z 表示 UTC
    const date = new Date(
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized)
            ? normalized
            : `${normalized}Z`
    );

    if (Number.isNaN(date.getTime())) return "";

    const now = new Date();

    const taiwanDate = new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Taipei",
        year: "numeric",
        month: "2-digit",
        day: "2-digit"
    });

    const today = taiwanDate.format(now);
    const messageDay = taiwanDate.format(date);

    if (messageDay === today) {
        return new Intl.DateTimeFormat("zh-TW", {
            timeZone: "Asia/Taipei",
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23"
        }).format(date);
    }

    const parts = Object.fromEntries(
        taiwanDate.formatToParts(date).map(part => [part.type, part.value])
    );

    const currentYear = new Intl.DateTimeFormat("en", {
        timeZone: "Asia/Taipei",
        year: "numeric"
    }).format(now);

    if (parts.year !== currentYear) {
        return `${parts.year}/${parts.month}/${parts.day}`;
    }

    return `${parts.month}/${parts.day}`;
}

// ==============================
// 載入目前會員的所有對話
// ==============================
async function loadConversations() {
    // 記錄本次對話列表請求版本
    const requestId = ++conversationsRequestId;

    if (!conversationsList) return;

    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入會員
    if (!token) {
        conversationsList.replaceChildren();

        const loginMessage = document.createElement("p");
        loginMessage.className = "messages-placeholder";
        loginMessage.textContent = "請先登入會員，才能查看訊息。";

        conversationsList.appendChild(loginMessage);
        return;
    }

    conversationsList.textContent = "載入對話中...";

    try {
        const response = await fetch("/api/conversations", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("取得對話列表失敗");
        }

        const data = await response.json();

        // 確認會員與請求版本沒有改變
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            requestId !== conversationsRequestId
        ) return;

        // 清空舊內容
        conversationsList.replaceChildren();

        // 尚無任何對話
        if (!data.conversations || data.conversations.length === 0) {
            const emptyMessage = document.createElement("p");
            emptyMessage.className = "messages-placeholder";
            emptyMessage.textContent = "目前還沒有任何對話紀錄";
            conversationsList.appendChild(emptyMessage);
            return;
        }

        // 依照 API 回傳順序建立對話卡片
        data.conversations.forEach((conversation) => {

            const item = document.createElement("button");
            item.type = "button";
            item.className = "conversation-item";
            item.dataset.conversationId = conversation.conversation_id;

            // 重新載入列表時，保留目前選取的對話
            if (Number(activeConversationId) === Number(conversation.conversation_id)) {
                item.classList.add("active");
            }

            // 記錄聊天對象的會員 ID
            item.dataset.partnerId = conversation.other_user_id;

            // 聊天對象名稱
            const name = document.createElement("strong");
            name.className = "conversation-name";
            name.textContent = conversation.other_user_name;

            // 最後一則訊息與傳送時間
            // 建立時間與訊息的外層容器
            const messageRow = document.createElement("div");
            messageRow.className = "conversation-message-row";

            // 訊息傳送時間
            const messageTime = document.createElement("span");
            messageTime.className = "conversation-time";
            messageTime.textContent = formatConversationTime(
                conversation.last_message_at
            );

            // 最後一則訊息
            const preview = document.createElement("p");
            preview.className = "conversation-preview";
            preview.textContent = conversation.last_message || "尚無訊息";

            // 有時間才顯示時間
            messageRow.appendChild(preview);

            // 傳送時間在右邊
            if (messageTime.textContent) {
                messageRow.appendChild(messageTime);
            }

            // 未讀訊息數量
            const unreadCount = Number(conversation.unread_count) || 0;

            // 保存實際未讀數量，避免顯示 99+ 時無法計算
            item.dataset.unreadCount = unreadCount;

            if (unreadCount > 0) {
                const badge = document.createElement("span");
                badge.className = "conversation-unread-badge";
                badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
                item.appendChild(badge);
            }

            item.appendChild(name);
            item.appendChild(messageRow);

            // 點擊對話後，載入右側聊天紀錄
            item.addEventListener("click", () => {

                // 移除其他對話的選取狀態
                document.querySelectorAll(".conversation-item").forEach((button) => {
                    button.classList.remove("active");
                });

                // 標記目前選取的對話
                item.classList.add("active");

                // 記錄目前正在聊天的對話 ID
                activeConversationId = conversation.conversation_id;

                // 手機版切換到聊天視窗
                if (messagesLayout) {
                    messagesLayout.classList.add("chat-open");
                }

                // 載入聊天紀錄
                loadConversationMessages(
                    conversation.conversation_id,
                    conversation.other_user_name,
                    conversation.other_user_id
                );

                // 立即更新左側與 Header 的未讀數字
                updateUnreadCountImmediately(conversation.conversation_id);

                // 將對話訊息標記為已讀
                markConversationAsRead(conversation.conversation_id);

            });


            conversationsList.appendChild(item);
        });

        // 從網址取得指定的對話 ID
        const urlParams = new URLSearchParams(window.location.search);
        const targetConversationId = urlParams.get("conversation_id");

        // 如果網址指定了對話，就自動開啟
        if (targetConversationId && /^[1-9]\d*$/.test(targetConversationId)) {

            const targetItem = Array.from(
                conversationsList.querySelectorAll(".conversation-item")
            ).find((item) =>
                item.dataset.conversationId === targetConversationId
            );

            if (targetItem) {
                // 沿用原本點擊對話的流程
                targetItem.click();

                // 清除網址參數，避免重新載入時重複指定
                window.history.replaceState(
                    null,
                    "",
                    window.location.pathname
                );
            }
        }

    } catch (error) {
        // 會員或請求版本已改變時，不更新畫面
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            requestId !== conversationsRequestId
        ) return;

        console.error("載入對話列表失敗：", error);
        conversationsList.textContent = "目前無法載入對話，請稍後再試。";
    }
}

// ==============================
// 即時更新未讀訊息數量
// ==============================
function updateUnreadCountImmediately(conversationId) {

    // 取得目前點選的對話
    const conversationItem = Array.from(
        document.querySelectorAll(".conversation-item")
    ).find((item) => Number(item.dataset.conversationId) === Number(conversationId));

    if (!conversationItem) return;

    // 取得這筆對話的未讀數量
    const conversationBadge = conversationItem.querySelector(".conversation-unread-badge");

    if (!conversationBadge) return;

    // 從 data-unread-count 取得實際未讀數量
    const unreadCount = Number(conversationItem.dataset.unreadCount);

    // 取得 Header 未讀數字
    const headerBadge = document.getElementById("message-unread-badge");

    if (!headerBadge) return;

    // 從 Header 的 data-unread-count 取得實際未讀總數
    const totalUnread = Number(headerBadge.dataset.unreadCount);

    // Header 未讀總數尚未載入完成時，交由後端同步
    if (
        !Number.isFinite(unreadCount) ||
        !Number.isFinite(totalUnread) ||
        unreadCount <= 0 ||
        totalUnread <= 0
    ) {
        // 先不扣除未讀數量，避免計算錯誤
        // 等待標記已讀 API 完成後重新取得正確數量
        return;
    }

    const remainingUnread = Math.max(0, totalUnread - unreadCount);

    // 讓先前尚未完成的 Header 未讀數量請求失效
    if (typeof unreadCountRequestId !== "undefined") {
        unreadCountRequestId++;
    }

    // 立即移除左側對話的未讀數字
    conversationBadge.remove();

    // 將這筆對話的未讀數量歸零
    conversationItem.dataset.unreadCount = "0";

    // 同步更新 Header 的實際未讀數量
    headerBadge.dataset.unreadCount = String(remainingUnread);

    // 立即更新 Header 未讀數字
    if (remainingUnread > 0) {
        headerBadge.textContent = remainingUnread > 99 ? "99+" : String(remainingUnread);
        headerBadge.hidden = false;
    } else {
        headerBadge.textContent = "";
        headerBadge.hidden = true;
    }
}

// ==============================
// 將指定對話的未讀訊息標記為已讀
// ==============================
async function markConversationAsRead(conversationId) {

    const token = sessionStorage.getItem("tutorlink_token");

    if (!token) return;

    try {
        const response = await fetch(
            `/api/conversations/${conversationId}/read`,
            {
                method: "PATCH",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            throw new Error("標記訊息已讀失敗");
        }

        // 確認目前登入會員沒有改變
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        // 已讀成功後，移除左側對話的未讀數字
        const conversationItem = Array.from(
            document.querySelectorAll(".conversation-item")
        ).find((item) => Number(item.dataset.conversationId) === Number(conversationId));

        if (conversationItem) {
            const badge = conversationItem.querySelector(".conversation-unread-badge");

            if (badge) {
                badge.remove();
            }
        }

        // 同步更新 Header 的未讀訊息數量
        if (typeof updateUnreadMessageCount === "function") {
            updateUnreadMessageCount();
        }

    } catch (error) {

        // 會員已切換時，不處理舊請求的錯誤
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        console.error("標記訊息已讀失敗：", error);

        // 標記已讀失敗時，重新取得正確的未讀數量
        await loadConversations();

        // 同步更新 Header 的未讀訊息數量
        if (typeof updateUnreadMessageCount === "function") {
            updateUnreadMessageCount();
        }
    }

}

// ==============================
// 家教預約系統：載入指定對話的聊天紀錄
// ==============================
async function loadConversationMessages(conversationId, partnerName, partnerId) {
    // 補齊目前聊天室的對話資訊，避免接受、拒絕預約後重新載入時缺少參數
    const activeItem = document.querySelector(
        ".conversation-item.active"
    );

    if (partnerName === undefined) {
        partnerName = activeItem?.querySelector(
            ".conversation-name"
        )?.textContent || "";
    }

    if (partnerId === undefined) {
        partnerId = activeItem?.dataset.partnerId;
    }

    // 記錄本次聊天紀錄請求版本
    const requestId = ++chatMessagesRequestId;

    const token = sessionStorage.getItem("tutorlink_token");

    const chatEmptyState = document.getElementById("chat-empty-state");
    const chatContent = document.getElementById("chat-content");
    const chatPartnerName = document.getElementById("chat-partner-name");
    const chatMessages = document.getElementById("chat-messages");

    if (!token || !chatContent || !chatMessages) return;

    // 顯示聊天區域
    chatEmptyState.hidden = true;
    chatContent.hidden = false;

    // 更新聊天對象名稱
    chatPartnerName.textContent = partnerName;

    // 載入提示
    chatMessages.textContent = "載入聊天紀錄中...";

    try {
        const response = await fetch(
            `/api/conversations/${conversationId}/messages`,
            {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            throw new Error("取得聊天紀錄失敗");
        }

        const data = await response.json();

        // 確認會員、對話與請求版本沒有改變
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            Number(activeConversationId) !== Number(conversationId) ||
            requestId !== chatMessagesRequestId
        ) {
            return;
        }

        chatMessages.replaceChildren();

        // 尚無訊息
        if (!data.messages || data.messages.length === 0) {
            const empty = document.createElement("p");
            empty.className = "messages-placeholder";
            empty.textContent = "目前還沒有訊息";
            chatMessages.appendChild(empty);
            return;
        }

        // 取得目前登入會員的 ID
        // 從目前對話的參與者身分判斷是否為預約老師
        // 目前會員必須不是對話中的另一方
        const currentPartnerId = Number(partnerId);

        // 顯示聊天訊息，區分自己與對方
        data.messages.forEach((message) => {

            const messageItem = document.createElement("div");
            messageItem.className = "chat-message-item";

            // 判斷訊息是否由對方傳送
            const isPartner = Number(message.sender_id) === Number(partnerId);

            if (isPartner) {
                messageItem.classList.add("received");
            } else {
                messageItem.classList.add("sent");
            }

            // 依照訊息類型顯示不同內容
            if (message.message_type === "booking") {

                // 建立預約卡片
                const card = document.createElement("div");
                card.className = "booking-message-card";

            // 家教預約卡片｜標題與預約狀態
            // 建立標題與狀態的外層容器
            const cardHeader = document.createElement("div");
            cardHeader.className = "booking-card-header";

            // 家教預約卡片｜辨識預約事件
            // 根據訊息內容判斷這筆預約事件
            const bookingEventMap = {
                "提出了一筆家教預約申請": "created",
                "接受了一筆家教預約申請": "accepted",
                "拒絕了一筆家教預約申請": "rejected",
                "取消了一筆家教預約": "cancelled"
            };

            // 舊訊息預設視為提出預約
            const bookingEvent =
                bookingEventMap[message.content] || "created";

            // 預約事件卡片｜顯示事件發生當下的狀態
            // 不因為後續接受、拒絕或取消而改變歷史紀錄
            const displayBookingStatus = {
                created: "pending",
                accepted: "accepted",
                rejected: "rejected",
                cancelled: "cancelled"
            }[bookingEvent];

            // 不同事件對應的卡片標題
            const bookingTitleMap = {
                created: "家教預約申請",
                accepted: "已接受預約",
                rejected: "已拒絕預約",
                cancelled: "已取消預約"
            };

            // 預約標題
            const title = document.createElement("h3");
            title.className = "booking-card-title";

            title.textContent =
                bookingTitleMap[bookingEvent];

            // 預約狀態
            const status = document.createElement("span");
            status.className = `booking-card-status ${displayBookingStatus}`;

            const statusLabels = {
                pending: "等待回覆",
                accepted: "已接受",
                rejected: "已拒絕",
                cancelled: "已取消"
            };

            status.textContent =
                statusLabels[displayBookingStatus] || "未知狀態";

            // 標題靠左、預約狀態靠右
            cardHeader.append(title, status);

                // 預約詳細資料
                const details = document.createElement("div");
                details.className = "booking-card-details";

                // 授課科目代碼與中文名稱對照
                const subjectLabels = {
                    math: "數學",
                    english: "英文",
                    chinese: "國文",
                    science: "自然",
                    social: "社會",
                    art: "美術",
                    music: "音樂",
                    other: "其他"
                };

                const subject =
                    subjectLabels[message.booking_subject] ||
                    message.booking_subject ||
                    "未提供";

                const date = message.booking_date
                    ? message.booking_date.replaceAll("-", "/")
                    : "未提供";

                // 統一預約時間格式為 HH:MM
                const formatBookingTime = (time) => {
                    if (!time) return "--:--";

                    const [hour, minute] = String(time).split(":");

                    return `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
                };

                const startTime = formatBookingTime(message.booking_start_time);
                const endTime = formatBookingTime(message.booking_end_time);

                const fields = [
                    ["授課科目", subject],
                    ["上課日期", date],
                    ["上課時間", `${startTime} - ${endTime}`],
                    ["課程長度", `${message.booking_duration_minutes} 分鐘`]
                ];

                fields.forEach(([label, value]) => {
                    const row = document.createElement("div");
                    row.className = "booking-card-detail-row";

                    const labelElement = document.createElement("span");
                    labelElement.textContent = label;

                    const valueElement = document.createElement("strong");
                    valueElement.textContent = value;

                    row.append(labelElement, valueElement);
                    details.appendChild(row);
                });

                // 課程金額
                const amount = document.createElement("div");
                amount.className = "booking-card-amount";

                const amountLabel = document.createElement("span");
                amountLabel.textContent = "課程總金額";

                const amountValue = document.createElement("strong");
                amountValue.textContent =
                    `NT$ ${Number(message.booking_total_amount).toLocaleString("en-US")}`;

                amount.append(amountLabel, amountValue);

                card.append(cardHeader, details, amount);

                // 老師操作預約按鈕
                // 只有等待回覆的預約才顯示操作按鈕
                // 如果預約老師是聊天對象，代表目前會員不是老師
                const isBookingTeacher =
                    Number(message.booking_teacher_user_id) !== currentPartnerId &&
                    Number(message.booking_teacher_user_id) > 0;

                // 判斷目前會員是否為預約學生
                // 目前會員不是聊天對象，因此預約學生若不是聊天對象，
                // 就代表目前登入者是這筆預約的學生
                const isBookingStudent =
                    Number(message.booking_student_id) > 0 &&
                    Number(message.booking_student_id) !== Number(currentPartnerId);

                if (
                    bookingEvent === "created" &&
                    message.booking_status === "pending" &&
                    isBookingTeacher
                ) {
                    const actions = document.createElement("div");
                    actions.className = "booking-card-actions";

                    const rejectButton = document.createElement("button");
                    rejectButton.type = "button";
                    rejectButton.className = "booking-reject-button";
                    rejectButton.textContent = "拒絕預約";

                    // 老師拒絕預約
                    rejectButton.addEventListener("click", async () => {

                        // 顯示 TutorLink 自訂確認視窗
                        const confirmed = await showBookingRejectModal();

                        if (!confirmed) return;

                        // 防止重複點擊
                        rejectButton.disabled = true;
                        acceptButton.disabled = true;

                        try {
                            // 取得 JWT
                            const token = sessionStorage.getItem("tutorlink_token");

                            if (!token) {
                                alert("請先登入會員");
                                return;
                            }

                            // 呼叫拒絕預約 API
                            const response = await fetch(
                                `/api/bookings/${message.booking_id}/reject`,
                                {
                                    method: "PATCH",
                                    headers: {
                                        "Authorization": `Bearer ${token}`
                                    }
                                }
                            );

                            const result = await response.json();

                            if (!response.ok) {
                                throw new Error(
                                    typeof result.detail === "string"
                                        ? result.detail
                                        : "拒絕預約失敗"
                                );
                            }

                            // 重新載入目前聊天室
                            await loadConversationMessages(message.conversation_id);

                        } catch (error) {
                            console.error("拒絕預約失敗：", error);
                            alert(error.message || "拒絕預約失敗");

                        } finally {
                            rejectButton.disabled = false;
                            acceptButton.disabled = false;
                        }
                    });

                    const acceptButton = document.createElement("button");
                    acceptButton.type = "button";
                    acceptButton.className = "booking-accept-button";
                    acceptButton.textContent = "接受預約";

                    // 老師接受預約
                    acceptButton.addEventListener("click", async () => {

                        // 防止重複點擊
                        acceptButton.disabled = true;

                        try {
                            // 取得登入會員的 JWT
                            const token = sessionStorage.getItem("tutorlink_token");

                            if (!token) {
                                alert("請先登入會員");
                                return;
                            }

                            // 呼叫接受預約 API
                            const response = await fetch(
                                `/api/bookings/${message.booking_id}/accept`,
                                {
                                    method: "PATCH",
                                    headers: {
                                        "Authorization": `Bearer ${token}`
                                    }
                                }
                            );

                            const result = await response.json();

                            if (!response.ok) {
                                throw new Error(
                                    typeof result.detail === "string"
                                        ? result.detail
                                        : "接受預約失敗"
                                );
                            }

                            // 重新載入聊天室，取得最新預約狀態
                            await loadConversationMessages(message.conversation_id);

                        } catch (error) {
                            console.error("接受預約失敗：", error);

                            await showBookingErrorModal(
                                error.message || "接受預約失敗，請稍後再試"
                            );

                        } finally {
                            acceptButton.disabled = false;
                        }
                    });

                    actions.append(rejectButton, acceptButton);
                    card.appendChild(actions);
                }

                // 學生只能在上課前一天（台灣時間）以前取消預約
                const taiwanDateParts = Object.fromEntries(
                    new Intl.DateTimeFormat("en-US", {
                        timeZone: "Asia/Taipei",
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit"
                    }).formatToParts(new Date()).map(part => [
                        part.type,
                        part.value
                    ])
                );

                const taiwanToday = [
                    taiwanDateParts.year,
                    taiwanDateParts.month,
                    taiwanDateParts.day
                ].join("-");

                const bookingDate = message.booking_date
                    ? String(message.booking_date).slice(0, 10)
                    : "";

                const canCancelByDate =
                    bookingDate !== "" &&
                    bookingDate > taiwanToday;

                // 學生取消預約按鈕
                // 待確認：顯示在學生提出的預約卡片、已接受：顯示在老師接受的預約卡片
                const isCurrentCancelableCard =
                    (
                        message.booking_status === "pending" &&
                        bookingEvent === "created"
                    ) ||
                    (
                        message.booking_status === "accepted" &&
                        bookingEvent === "accepted"
                    );

                if (
                    isBookingStudent &&
                    isCurrentCancelableCard &&
                    canCancelByDate
                ) {
                    const cancelActions = document.createElement("div");
                    cancelActions.className = "booking-card-actions";

                    const cancelBookingButton = document.createElement("button");
                    cancelBookingButton.type = "button";
                    cancelBookingButton.className = "booking-reject-button";
                    cancelBookingButton.textContent = "取消預約";

                    // 學生取消預約
                    cancelBookingButton.addEventListener("click", async () => {

                        // 顯示 TutorLink 自訂確認視窗
                        const confirmed = await showBookingCancelModal();

                        // 點擊返回或關閉視窗，不執行取消
                        if (!confirmed) return;

                        // 防止重複點擊
                        cancelBookingButton.disabled = true;

                        try {
                            const token = sessionStorage.getItem("tutorlink_token");

                            if (!token) {
                                throw new Error("請先登入會員");
                            }

                            // 呼叫取消預約 API
                            const response = await fetch(
                                `/api/bookings/${message.booking_id}/cancel`,
                                {
                                    method: "PATCH",
                                    headers: {
                                        "Authorization": `Bearer ${token}`
                                    }
                                }
                            );

                            const result = await response.json();

                            if (!response.ok) {
                                throw new Error(
                                    typeof result.detail === "string"
                                        ? result.detail
                                        : "取消預約失敗"
                                );
                            }

                            // 取得目前聊天室的對話資訊
                            const activeItem = document.querySelector(
                                ".conversation-item.active"
                            );

                            // 取消成功後重新載入聊天紀錄
                            if (
                                activeItem &&
                                Number(activeConversationId) === Number(message.conversation_id)
                            ) {
                                const partnerName = activeItem.querySelector(
                                    ".conversation-name"
                                )?.textContent;

                                const partnerId = activeItem.dataset.partnerId;

                                await loadConversationMessages(
                                    message.conversation_id,
                                    partnerName,
                                    partnerId
                                );
                            }

                        } catch (error) {
                            console.error("取消預約失敗：", error);
                            alert(error.message || "取消預約失敗");

                        } finally {
                            cancelBookingButton.disabled = false;
                        }
                    });

                    cancelActions.appendChild(cancelBookingButton);
                    card.appendChild(cancelActions);
                }

                messageItem.appendChild(card);

            } else {

                // 原本的一般文字訊息
                const bubble = document.createElement("div");
                bubble.className = "chat-message-bubble";
                bubble.textContent = message.content;

                messageItem.appendChild(bubble);
            }

            chatMessages.appendChild(messageItem);
        });

        // 捲動到最新訊息
        chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch (error) {
        // 會員、對話或請求版本已改變時，不更新畫面
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            Number(activeConversationId) !== Number(conversationId) ||
            requestId !== chatMessagesRequestId
        ) {
            return;
        }

        console.error("載入聊天紀錄失敗：", error);
        chatMessages.textContent = "目前無法載入聊天紀錄，請稍後再試。";
    }

}

// ==============================
// 傳送聊天訊息
// ==============================

// 取得聊天表單與輸入框
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

// 監聽聊天表單送出
if (chatForm && chatInput) {

    chatForm.addEventListener("submit", async (event) => {

        // 防止表單送出後重新整理頁面
        event.preventDefault();

        // 取得目前輸入的訊息
        const content = chatInput.value.trim();

        // 沒有選取對話，或訊息為空白時，不傳送
        if (!activeConversationId || !content) return;

        // 取得登入 Token
        const token = sessionStorage.getItem("tutorlink_token");

        if (!token) {
            alert("請先登入會員");
            return;
        }

        // 同一位會員已有訊息正在傳送時，避免重複提交
        if (sendingMessageToken === token) return;

        // 記錄目前正在傳送訊息的會員
        sendingMessageToken = token;

        // 記錄這次要傳送的對話 ID
        const conversationId = activeConversationId;

        // 避免重複點擊傳送按鈕
        const sendButton = chatForm.querySelector('button[type="submit"]');

        if (sendButton) {
            sendButton.disabled = true;
        }

        try {
            // 呼叫後端傳送訊息 API
            const response = await fetch(
                `/api/conversations/${conversationId}/messages`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        content: content
                    })
                }
            );

            if (!response.ok) {
                throw new Error("訊息傳送失敗");
            }

            // 會員已切換時，不更新目前的聊天畫面
            if (sessionStorage.getItem("tutorlink_token") !== token) {
                return;
            }

            // 傳送成功後清空輸入框
            // 若使用者已切換對話或修改輸入內容，則不清空
            if (
                activeConversationId === conversationId &&
                chatInput.value.trim() === content
            ) {
                chatInput.value = "";
            }

            // 更新左側對話列表的最後訊息與時間
            const conversationItem = Array.from(
                document.querySelectorAll(".conversation-item")
            ).find((item) => Number(item.dataset.conversationId) === Number(conversationId));

            if (conversationItem) {
                const preview = conversationItem.querySelector(".conversation-preview");
                const time = conversationItem.querySelector(".conversation-time");

                if (preview) {
                    preview.textContent = content;
                }

                if (time) {
                    time.textContent = formatConversationTime(
                        new Date().toISOString()
                    );
                }
            }

            // 如果仍停留在同一筆對話，重新載入聊天紀錄
            if (activeConversationId === conversationId) {
                const activeItem = document.querySelector(".conversation-item.active");

                if (activeItem) {
                    const partnerName = activeItem.querySelector(".conversation-name")?.textContent;
                    const partnerId = activeItem.dataset.partnerId;

                    await loadConversationMessages(
                        conversationId,
                        partnerName,
                        partnerId
                    );
                }
            }

        } catch (error) {
            // 會員已切換時，不顯示上一位會員的錯誤
            if (sessionStorage.getItem("tutorlink_token") !== token) {
                return;
            }

            console.error("傳送訊息失敗：", error);
            alert("訊息傳送失敗，請稍後再試。");

        } finally {
            // 只有目前這筆請求可以清除傳送狀態
            if (sendingMessageToken === token) {
                sendingMessageToken = null;
            }

            // 只有目前會員的請求可以恢復傳送按鈕
            if (
                sendButton &&
                sessionStorage.getItem("tutorlink_token") === token
            ) {
                sendButton.disabled = false;
            }
        }
    });
}

// ==============================
// 手機版返回對話列表
// ==============================
if (chatBackButton && messagesLayout) {

    chatBackButton.addEventListener("click", () => {

        // 返回對話列表
        messagesLayout.classList.remove("chat-open");

    });
}

// ==============================
// 會員登出後清除聊天畫面
// ==============================
window.addEventListener("tutorlink:logout", () => {

    // 清除上一位會員的聊天資料
    clearMessagesPage();

    // 顯示未登入提示
    loadConversations();

});

// ==============================
// 會員登入後重新載入對話
// ==============================
window.addEventListener("tutorlink:login", () => {

    // 清除上一位會員的聊天資料
    clearMessagesPage();

    // 載入目前會員的對話列表
    loadConversations();

});

// ==============================
// 頁面載入後取得對話列表
// ==============================
document.addEventListener("DOMContentLoaded", loadConversations);