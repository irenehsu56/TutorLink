if (window.lucide) {lucide.createIcons();}

// ==============================
// TutorLink 評價通知中心
// ==============================
document.addEventListener("DOMContentLoaded", () => {

    const loading = document.getElementById(
        "notifications-loading"
    );

    const loginRequired = document.getElementById(
        "notifications-login-required"
    );

    const loginButton = document.getElementById(
        "notifications-login-button"
    );

    const notificationList = document.getElementById(
        "notifications-list"
    );

    const empty = document.getElementById(
        "notifications-empty"
    );

    const errorMessage = document.getElementById(
        "notifications-error"
    );

    let requestId = 0;

    // 切換頁面顯示狀態
    function showState(state) {
        loading.hidden = state !== "loading";
        loginRequired.hidden = state !== "login";
        empty.hidden = state !== "empty";
        errorMessage.hidden = state !== "error";

        document.body.classList.toggle(
            "member-login-required",
            state === "login"
        );

        if (state === "login" && window.lucide) {
            lucide.createIcons();
        }
    }

    // 通知類型對應文字
    const notificationTypes = {
        review_available: {
            title: "課程已完成，可以發表評價",
            description: "你的課程已完成，歡迎分享學習心得。",
            icon: "clipboard-check"
        },

        review_created: {
            title: "收到新的學生評價",
            description: "有學生發表了新的課後評價，點擊查看。",
            icon: "message-square"
        },

        review_replied: {
            title: "老師已回覆你的評價",
            description: "老師已回覆你的課後評價，點擊查看。",
            icon: "message-circle"
        }
    };

    // 格式化通知時間
    // 後端時間若未含時區，依資料庫 UTC 儲存處理
    function formatNotificationTime(value) {
        if (!value) return "";

        const raw = String(value).trim();

        const normalized = raw.includes("T")
            ? raw
            : raw.replace(" ", "T");

        const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(
            normalized
        );

        const date = new Date(
            hasTimezone ? normalized : normalized + "Z"
        );

        if (Number.isNaN(date.getTime())) {
            return raw;
        }

        return new Intl.DateTimeFormat("zh-TW", {
            timeZone: "Asia/Taipei",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
        }).format(date);
    }

    // 建立單筆通知卡片
    function createNotificationItem(notification) {

        const config = notificationTypes[
            notification.event_type
        ] || {
            title: "評價通知",
            description: "你有一則新的評價通知。",
            icon: "bell"
        };

        const isUnread = !Boolean(notification.is_read);

        const item = document.createElement("div");

        item.className = "notification-item";

        if (isUnread) {
            item.classList.add("unread");
        }

        item.dataset.notificationId = notification.id;
        item.dataset.bookingId = notification.booking_id;
        item.dataset.teacherId = notification.teacher_id ?? "";
        item.dataset.reviewId = notification.review_id ?? "";
        item.dataset.eventType = notification.event_type;

        // 通知圖示
        const iconWrapper = document.createElement("div");
        iconWrapper.className = "notification-icon";

        const icon = document.createElement("i");
        icon.setAttribute("data-lucide", config.icon);

        iconWrapper.appendChild(icon);

        // 通知文字
        const body = document.createElement("div");
        body.className = "notification-body";

        const title = document.createElement("div");
        title.className = "notification-title";
        title.textContent = config.title;

        const description = document.createElement("p");
        description.className = "notification-description";
        description.textContent = config.description;

        const time = document.createElement("div");
        time.className = "notification-time";
        time.textContent = formatNotificationTime(
            notification.created_at
        );

        // 標題與時間排列在同一行
        const titleRow = document.createElement("div");
        titleRow.className = "notification-title-row";

        titleRow.append(title, time);

        body.append(titleRow, description);

        // 未讀紅點
        const unreadDot = document.createElement("span");
        unreadDot.className = "notification-unread-dot";
        unreadDot.hidden = !isUnread;
        unreadDot.setAttribute("aria-label", "未讀通知");

        item.append(iconWrapper, body, unreadDot);

        return item;
    }

    // 載入會員通知
    async function loadNotifications() {

        const currentRequestId = ++requestId;

        const token = sessionStorage.getItem(
            "tutorlink_token"
        );

        notificationList.replaceChildren();

        if (!token) {
            showState("login");
            return;
        }

        showState("loading");

        try {
            const response = await fetch(
                "/api/review-notifications",
                {
                    headers: {
                        Authorization: `Bearer ${token}`
                    },
                    cache: "no-store"
                }
            );

            if (!response.ok) {
                throw new Error(
                    `讀取通知失敗：${response.status}`
                );
            }

            const data = await response.json();

            // 避免登出或切換帳號後顯示舊資料
            if (
                currentRequestId !== requestId ||
                sessionStorage.getItem("tutorlink_token") !== token
            ) {
                return;
            }

            const notifications = Array.isArray(
                data.notifications
            ) ? data.notifications : [];

            if (notifications.length === 0) {
                showState("empty");
                return;
            }

            const fragment = document.createDocumentFragment();

            notifications.forEach((notification) => {
                fragment.appendChild(
                    createNotificationItem(notification)
                );
            });

            notificationList.replaceChildren(fragment);

            showState("ready");

            // 初始化 Lucide 圖示
            if (window.lucide) {
                lucide.createIcons();
            }

        } catch (error) {

            if (
                currentRequestId !== requestId ||
                sessionStorage.getItem("tutorlink_token") !== token
            ) {
                return;
            }

            console.error("通知中心載入失敗：", error);

            notificationList.replaceChildren();
            showState("error");
        }
    }

    // 未登入時，開啟既有登入視窗
    if (loginButton) {
        loginButton.addEventListener("click", () => {
            const existingLoginButton = document.querySelector(
                '[data-auth-open="login"]'
            );

            if (existingLoginButton) {
                existingLoginButton.click();
            }
        });
    }

    // 點擊通知：標記已讀並前往老師評價區
    notificationList.addEventListener("click", async (event) => {

        const item = event.target.closest(".notification-item");

        if (!item || item.dataset.processing === "true") {
            return;
        }

        const notificationId = Number(item.dataset.notificationId);
        const teacherId = Number(item.dataset.teacherId);

        if (
            !Number.isSafeInteger(notificationId) ||
            notificationId <= 0 ||
            !Number.isSafeInteger(teacherId) ||
            teacherId <= 0
        ) {
            console.error("通知缺少有效 ID");
            return;
        }

        const token = sessionStorage.getItem("tutorlink_token");

        if (!token) {
            loadNotifications();
            return;
        }

        const targetUrl = new URL(
            "/teacher-detail.html",
            window.location.origin
        );

        targetUrl.searchParams.set("id", String(teacherId));

        // 如果通知有對應的評價 ID，一起帶到老師詳細頁
        const reviewId = Number(item.dataset.reviewId);

        if (Number.isSafeInteger(reviewId) && reviewId > 0) {
            targetUrl.searchParams.set("review_id", String(reviewId));
        }

        targetUrl.hash = "detail-reviews-section";

        item.dataset.processing = "true";

        try {
            // 只有未讀通知才需要呼叫已讀 API
            if (item.classList.contains("unread")) {
                const response = await fetch(
                    `/api/review-notifications/${notificationId}/read`,
                    {
                        method: "POST",
                        headers: {
                            Authorization: `Bearer ${token}`
                        },
                        cache: "no-store"
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `標記通知已讀失敗：${response.status}`
                    );
                }

                if (
                    sessionStorage.getItem("tutorlink_token") !== token
                ) {
                    loadNotifications();
                    return;
                }

                item.classList.remove("unread");

                const unreadDot = item.querySelector(
                    ".notification-unread-dot"
                );

                if (unreadDot) {
                    unreadDot.hidden = true;
                }

                if (
                    typeof updateCourseNotificationDots === "function"
                ) {
                    updateCourseNotificationDots();
                }
            }

            // 已讀與未讀通知都可以跳轉
            if (
                sessionStorage.getItem("tutorlink_token") === token
            ) {
                window.location.assign(targetUrl.toString());
            }

        } catch (error) {
            console.error("處理通知點擊失敗：", error);
            alert("通知處理失敗，請稍後再試。");

        } finally {
            item.dataset.processing = "false";
        }
    });

    // 頁面初始化
    loadNotifications();

    // 切回分頁時重新取得最新通知
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            loadNotifications();
        }
    });

    // 會員登入／登出即時同步通知中心
    // 登入成功：重新載入目前會員的通知
    window.addEventListener("tutorlink:login", () => {
        loadNotifications();
    });

    // 登出成功：清除舊通知並顯示登入提示
    window.addEventListener("tutorlink:logout", () => {
        loadNotifications();
    });

    // 保留原本提供給其他功能使用的更新方法
    window.refreshReviewNotifications = loadNotifications;

});
