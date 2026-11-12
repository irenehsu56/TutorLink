// ==============================
// Auth Modal 會員登入／註冊功能
// ==============================

// 取得整個會員視窗
const authModal = document.getElementById("auth-modal");
// 取得所有開啟會員視窗的按鈕
const authOpenButtons = document.querySelectorAll("[data-auth-open]");
// 取得所有關閉會員視窗的元素
const authCloseButtons = document.querySelectorAll("[data-auth-close]");

// 記錄開啟視窗前，使用者正在操作的元素
let previousFocusedElement = null;

// ==============================
// 登入／註冊表單切換
// ==============================

// 取得登入、註冊頁籤
const authTabs = document.querySelectorAll("[data-auth-tab]");

// 取得登入、註冊表單區域
const loginPanel = document.getElementById("auth-login-panel");
const registerPanel = document.getElementById("auth-register-panel");

// 取得標題與說明文字
const authTitle = document.getElementById("auth-title");
const authDescription = document.getElementById("auth-description");

function switchAuthTab(mode) {
    // 判斷是否切換到登入表單
    const isLogin = mode === "login";

    // 控制表單顯示或隱藏
    loginPanel.hidden = !isLogin;
    registerPanel.hidden = isLogin;

    // 更新視窗標題與說明
    authTitle.textContent = isLogin
        ? "歡迎回到 TutorLink"
        : "加入 TutorLink";

    authDescription.textContent = isLogin
        ? "登入帳號，開始尋找適合的家教老師"
        : "建立帳號，開啟你的家教媒合旅程";

    // 更新頁籤的選取狀態
    authTabs.forEach((tab) => {

        const isActive = tab.dataset.authTab === mode;

        // 切換橘色背景樣式
        tab.classList.toggle("active", isActive);

        // 更新無障礙選取狀態
        tab.setAttribute("aria-selected", String(isActive));

        // 選取的頁籤可使用 Tab 到達
        tab.tabIndex = isActive ? 0 : -1;

    });
}

// ==============================
// 點擊頁籤切換登入／註冊
// ==============================
authTabs.forEach((tab) => {

    tab.addEventListener("click", () => {

        const mode = tab.dataset.authTab;

        switchAuthTab(mode);

    });

});

// ==============================
// 使用左右方向鍵切換頁籤
// ==============================
authTabs.forEach((tab) => {

    tab.addEventListener("keydown", (event) => {

        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
            return;
        }

        // 阻止方向鍵的預設操作
        event.preventDefault();

        // 目前只有兩個頁籤，方向鍵切換至另一個
        const nextMode = tab.dataset.authTab === "login"
            ? "register"
            : "login";

        switchAuthTab(nextMode);

        // 將焦點移到新的頁籤
        document.querySelector(
            `[data-auth-tab="${nextMode}"]`
        ).focus();

    });

});

// ==============================
// 開啟會員視窗
// ==============================
function openAuthModal(mode = "login") {
    // 記住開啟視窗前的焦點
    previousFocusedElement = document.activeElement;

    // 根據點擊的按鈕，切換登入或註冊表單
    switchAuthTab(mode);

    // 顯示會員視窗
    authModal.hidden = false;

    // 將焦點移到目前表單的第一個輸入欄位
    const firstInput = mode === "register"
        ? document.getElementById("register-name")
        : document.getElementById("login-email");

    firstInput.focus();
}

// ==============================
// 關閉會員視窗
// ==============================
function closeAuthModal() {
    // 加上 hidden，隱藏會員視窗
    authModal.hidden = true;

    // 將焦點還給原本點擊的按鈕
    previousFocusedElement?.focus();
}

// ==============================
// 綁定開啟按鈕
// ==============================
authOpenButtons.forEach((button) => {

    button.addEventListener("click", () => {

        // 取得按鈕上的 data-auth-open
        const mode = button.dataset.authOpen;

        // 開啟對應的會員表單
        openAuthModal(mode);
    });

});

// ==============================
// 綁定關閉按鈕
// ==============================
authCloseButtons.forEach((button) => {

    button.addEventListener("click", () => {
        closeAuthModal();
    });

});

// ==============================
// 按下 Esc 關閉會員視窗
// ==============================
document.addEventListener("keydown", (event) => {

    if (event.key === "Escape" && !authModal.hidden) {
        closeAuthModal();
    }

});

// ==============================
// 會員視窗開啟時，限制 Tab 焦點留在視窗內
// ==============================
authModal.addEventListener("keydown", (event) => {

    if (event.key !== "Tab") {
        return;
    }

    // 取得視窗內目前可操作、可見的元素
    const focusableElements = Array.from(
        authModal.querySelectorAll(
            'button:not(:disabled), input:not(:disabled), a[href], select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
        )
    ).filter((element) => element.getClientRects().length > 0);

    if (focusableElements.length === 0) {
        return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    // Shift + Tab：從第一個元素跳回最後一個
    if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
    }

    // Tab：從最後一個元素跳回第一個
    else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
    }

});

// ==============================
// 會員註冊功能
// ==============================

// 取得註冊表單與訊息顯示區域
const registerForm = document.getElementById("auth-register-form");
const registerMessage = document.getElementById("register-message");

// 監聽註冊表單的送出事件
registerForm.addEventListener("submit", async (event) => {

    // 阻止瀏覽器預設的表單送出行為
    event.preventDefault();

    // 取得使用者輸入的資料
    const name = document.getElementById("register-name").value.trim();
    const email = document.getElementById("register-email").value.trim();
    const password = document.getElementById("register-password").value;
    const confirmPassword = document.getElementById("register-confirm-password").value;

    // 清除上一次的提示訊息
    registerMessage.textContent = "";
    registerMessage.classList.remove("success");

    // 檢查兩次密碼是否一致
    if (password !== confirmPassword) {
        registerMessage.textContent = "兩次輸入的密碼不一致";
        return;
    }

    // 取得註冊按鈕
    const submitButton = registerForm.querySelector(".auth-submit");

    // 防止使用者重複送出
    submitButton.disabled = true;
    submitButton.textContent = "註冊中...";

    try {

        // 發送註冊請求到 FastAPI
        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                email: email,
                password: password
            })
        });

        // 取得後端回傳的 JSON
        const data = await response.json();

        // 註冊失敗
        if (!response.ok) {

            // 409：Email 已經被註冊
            if (response.status === 409) {
                registerMessage.textContent = "這個 Email 已經被註冊";
            } else {
                registerMessage.textContent = "註冊失敗，請確認資料後再試";
            }

            return;
        }

        // 註冊成功，清空表單
        registerForm.reset();

        // 切換到登入表單
        switchAuthTab("login");

        // 在登入表單顯示成功訊息
        const loginMessage = document.getElementById("login-message");

        loginMessage.textContent = "註冊成功！請登入你的帳號";
        loginMessage.classList.add("success");

        // 將焦點移到登入 Email 欄位
        document.getElementById("login-email").focus();

    } catch (error) {

        // 網路錯誤或伺服器無法連線
        console.error("註冊發生錯誤：", error);

        registerMessage.textContent = "無法連接伺服器，請稍後再試";

    } finally {

        // 不論成功或失敗，都恢復註冊按鈕
        submitButton.disabled = false;
        submitButton.textContent = "建立帳號";

    }

});

// ==============================
// 會員登入功能
// ==============================

// 取得登入表單與訊息顯示區域
const loginForm = document.getElementById("auth-login-form");
const loginMessage = document.getElementById("login-message");

// 監聽登入表單送出事件
loginForm.addEventListener("submit", async (event) => {

    // 阻止瀏覽器重新整理頁面
    event.preventDefault();

    // 取得使用者輸入的 Email 和密碼
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    // 清除之前的提示訊息
    loginMessage.textContent = "";
    loginMessage.classList.remove("success");

    // 取得登入按鈕
    const submitButton = loginForm.querySelector(".auth-submit");

    // 防止重複送出
    submitButton.disabled = true;

    try {

        // 呼叫 FastAPI 登入 API
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        // 取得後端回傳資料
        const data = await response.json();

        // 登入失敗
        if (!response.ok) {

            if (response.status === 401) {
                loginMessage.textContent = "電子郵件或密碼錯誤";
            } else {
                loginMessage.textContent = "登入失敗，請稍後再試";
            }

            return;
        }

        // 確認後端有回傳 JWT
        if (!data.access_token) {
            loginMessage.textContent = "登入回應異常，請稍後再試";
            return;
        }

        // 儲存 JWT
        sessionStorage.setItem("tutorlink_token", data.access_token);

        // 通知其他頁面功能：會員已登入成功
        window.dispatchEvent(new Event("tutorlink:login"));

        // 透過後端確認登入身分並更新 Header
        await loadCurrentUser();

        // 清空登入表單
        loginForm.reset();

        // 關閉會員視窗
        closeAuthModal();

        // 顯示登入成功通知
        showAuthToast("登入成功！", "歡迎回到 TutorLink");

    } catch (error) {

        console.error("登入發生錯誤：", error);

        loginMessage.textContent = "無法連接伺服器，請稍後再試";

    } finally {

        // 恢復登入按鈕
        submitButton.disabled = false;

    }

});

// ==============================
// Toast 網站通知
// ==============================
let authToastTimer = null;

function showAuthToast(title, message) {

    // 如果已經有通知，先移除
    const oldToast = document.querySelector(".auth-toast");

    if (oldToast) {
        oldToast.remove();
    }

    // 清除上一個通知的計時器
    clearTimeout(authToastTimer);

    // 建立通知元素
    const toast = document.createElement("div");

    toast.className = "auth-toast";
    toast.setAttribute("role", "status");

    // 建立圖示區域
    const icon = document.createElement("div");
    icon.className = "auth-toast-icon";
    icon.textContent = "✓";

    // 建立文字區域
    const content = document.createElement("div");
    content.className = "auth-toast-content";

    const titleElement = document.createElement("strong");
    titleElement.textContent = title;

    const messageElement = document.createElement("p");
    messageElement.textContent = message;

    content.append(titleElement, messageElement);
    toast.append(icon, content);

    // 加入網頁
    document.body.appendChild(toast);

    // 3 秒後自動移除
    authToastTimer = setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ==============================
// 課程未讀提醒紅點
// ==============================
let courseNotificationRequestId = 0;

// 更新課程與評價通知紅點
async function updateCourseNotificationDots() {
    const requestId = ++courseNotificationRequestId;

    const memberDot = document.getElementById(
        "member-notification-dot"
    );

    const calendarDot = document.getElementById(
        "member-calendar-dot"
    );

    const reviewDot = document.getElementById(
        "member-review-notification-dot"
    );

    const token = sessionStorage.getItem("tutorlink_token");

    // 先清除舊帳號的通知狀態
    if (memberDot) memberDot.hidden = true;
    if (calendarDot) calendarDot.hidden = true;
    if (reviewDot) reviewDot.hidden = true;

    if (!token) return;

    try {
        // 同時取得課程與評價的未讀狀態
        const [courseResponse, reviewResponse] = await Promise.all([
            fetch("/api/course-notifications/unread", {
                headers: {
                    Authorization: `Bearer ${token}`
                },
                cache: "no-store"
            }),
            fetch("/api/review-notifications/unread", {
                headers: {
                    Authorization: `Bearer ${token}`
                },
                cache: "no-store"
            })
        ]);

        if (!courseResponse.ok || !reviewResponse.ok) {
            throw new Error(
                `通知查詢失敗：課程 ${courseResponse.status}，評價 ${reviewResponse.status}`
            );
        }

        const [courseData, reviewData] = await Promise.all([
            courseResponse.json(),
            reviewResponse.json()
        ]);

        // 避免舊請求覆蓋新帳號狀態
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            requestId !== courseNotificationRequestId
        ) {
            return;
        }

        const hasCourseUnread = courseData.has_unread === true;
        const hasReviewUnread = reviewData.has_unread === true;

        // 課程紅點只受課程通知影響
        if (calendarDot) {
            calendarDot.hidden = !hasCourseUnread;
        }

        // 通知中心紅點只受評價通知影響
        if (reviewDot) {
            reviewDot.hidden = !hasReviewUnread;
        }

        // 會員按鈕：任一類未讀就顯示
        if (memberDot) {
            memberDot.hidden = !(hasCourseUnread || hasReviewUnread);
        }

    } catch (error) {
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            requestId !== courseNotificationRequestId
        ) {
            return;
        }

        console.error("更新通知紅點失敗：", error);

        if (memberDot) memberDot.hidden = true;
        if (calendarDot) calendarDot.hidden = true;
        if (reviewDot) reviewDot.hidden = true;
    }
}

// ==============================
// Member 會員登入狀態管理
// ==============================
// 取得 Header 會員相關元素
const memberMenu = document.getElementById("member-menu");
const memberTrigger = document.getElementById("member-trigger");
const memberName = document.getElementById("member-name");
const memberDropdown = document.getElementById("member-dropdown");
const memberLogout = document.getElementById("member-logout");

// Header 會員頭貼
const memberAvatar = document.getElementById("member-avatar");

// Header：成為家教／我的家教資料
const navTeacherLink = document.getElementById("nav-teacher-link");

// ==============================
// 更新 Header 會員頭貼
// ==============================
function updateMemberAvatar(photoUrl = null) {

    if (!memberAvatar) return;

    // 清除舊會員的頭貼或圖示
    memberAvatar.replaceChildren();

    // 沒有頭貼時顯示預設會員圖示
    function showDefaultAvatar() {
        memberAvatar.replaceChildren();

        const icon = document.createElement("i");
        icon.setAttribute("data-lucide", "circle-user-round");

        memberAvatar.appendChild(icon);

        if (window.lucide) {
            lucide.createIcons();
        }
    }

    if (!photoUrl) {
        showDefaultAvatar();
        return;
    }

    // 建立會員頭貼圖片
    const image = document.createElement("img");
    image.alt = "會員頭貼";

    // 圖片失效時恢復預設圖示
    image.onerror = () => {
        if (memberAvatar.contains(image)) {
            showDefaultAvatar();
        }
    };

    image.src = photoUrl;
    memberAvatar.appendChild(image);
}

// ==============================
// 更新 Header 會員畫面
// ==============================
function updateMemberUI(user = null) {

    // 判斷使用者是否已登入
    const isLoggedIn = user !== null;

    // 根據會員身分更新老師入口名稱與連結
    if (navTeacherLink) {
        const isTeacher = isLoggedIn && user.role === "teacher";

        // 更新 Header 顯示文字
        navTeacherLink.textContent = isTeacher
            ? "我的家教資料"
            : "成為家教";

        // 根據會員身分設定導覽列連結
        navTeacherLink.href = isTeacher
            ? "/my-teacher-profile.html"
            : "/become-teacher.html";
    }

    // 登入／註冊按鈕：登入後隱藏
    authOpenButtons.forEach((button) => {
        button.hidden = isLoggedIn;
    });

    // 會員選單：登入後顯示
    memberMenu.hidden = !isLoggedIn;

    // Header 私訊入口顯示控制
    const headerMessageLink = document.getElementById("header-message-link");

    // 登入後顯示訊息圖示，登出後隱藏
    if (headerMessageLink) {
        headerMessageLink.hidden = !isLoggedIn;
    }

    // 更新 Header 未讀訊息數量
    updateUnreadMessageCount();

    // 更新會員課程提醒紅點
    updateCourseNotificationDots();

    if (isLoggedIn) {

        // 顯示後端回傳的會員名稱
        memberName.textContent = user.name;

        // 顯示目前登入會員的頭貼
        updateMemberAvatar(user.photo_url || null);

    } else {

        // 登出後恢復預設狀態
        memberName.textContent = "會員名稱";

        // 清除上一位會員的頭貼
        updateMemberAvatar();

    }

    // 收起會員下拉選單
    closeMemberDropdown();
}

// ==============================
// 更新 Header 未讀訊息數量
// ==============================
let unreadCountRequestId = 0;

async function updateUnreadMessageCount() {
    // 記錄本次請求版本，避免舊請求覆蓋新結果
    const requestId = ++unreadCountRequestId;

    const badge = document.getElementById("message-unread-badge");
    const messageLink = document.getElementById("header-message-link");

    if (!badge || !messageLink) return;

    const token = sessionStorage.getItem("tutorlink_token");

    // 登入會員改變時，先清除上一位會員的未讀數量
    if (badge.dataset.token !== (token || "")) {
        badge.hidden = true;
        badge.textContent = "";
        badge.dataset.unreadCount = "0";
        badge.dataset.token = token || "";
    }

    // 未登入時隱藏未讀數字
    if (!token || messageLink.hidden) {
        badge.hidden = true;
        badge.textContent = "";
        badge.dataset.unreadCount = "0";
        return;
    }

    try {
        const response = await fetch("/api/messages/unread-count", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("取得未讀訊息數量失敗");
        }

        const data = await response.json();
        const unreadCount = Number(data.unread_count) || 0;

        // 若會員已切換或已有較新的請求，不更新畫面
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            messageLink.hidden ||
            requestId !== unreadCountRequestId
        ) {
            return;
        }

        // 保存 Header 實際未讀數量
        badge.dataset.unreadCount = String(unreadCount);

        if (unreadCount > 0) {
            badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
            badge.hidden = false;
        } else {
            badge.textContent = "";
            badge.hidden = true;
        }

    } catch (error) {
        // 舊請求失敗時，不影響目前的未讀數字
        if (
            sessionStorage.getItem("tutorlink_token") !== token ||
            requestId !== unreadCountRequestId
        ) {
            return;
        }

        console.error("更新未讀訊息數量失敗：", error);
        badge.hidden = true;
        badge.textContent = "";
        badge.dataset.unreadCount = "0";
    }
}

// ==============================
// 收起會員下拉選單
// ==============================
function closeMemberDropdown() {

    memberDropdown.hidden = true;
    memberTrigger.setAttribute("aria-expanded", "false");

}

// ==============================
// 取得目前登入的會員資料
// ==============================
window.addEventListener("tutorlink:profile-updated", () => {
    loadCurrentUser();
});

async function loadCurrentUser() {

    // 從 sessionStorage 取得 JWT
    const token = sessionStorage.getItem("tutorlink_token");

    // 沒有 Token，表示尚未登入
    if (!token) {
        updateMemberUI();
        return;
    }

    try {

        // 呼叫 FastAPI 驗證會員身分
        const response = await fetch("/api/auth/me", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        // Token 已失效或過期
        if (response.status === 401 || response.status === 403) {

            // 只有目前會員的 Token 失效，才清除登入狀態
            if (sessionStorage.getItem("tutorlink_token") !== token) return;

            sessionStorage.removeItem("tutorlink_token");
            updateMemberUI();

            // 通知其他頁面清除舊會員資料
            window.dispatchEvent(new Event("tutorlink:logout"));
            return;
        }

        // 其他伺服器錯誤
        if (!response.ok) {
            console.error("取得會員資料失敗：", response.status);
            return;
        }

        // 取得會員資料
        const data = await response.json();

        // 登入會員已改變時，不使用舊請求的會員資料
        if (sessionStorage.getItem("tutorlink_token") !== token) return;

        // 更新 Header
        updateMemberUI(data.user);

    } catch (error) {

        // 網路異常不代表 Token 一定失效
        console.error("無法取得會員資料：", error);

    }

}

// ==============================
// 展開／收起會員選單
// ==============================
memberTrigger.addEventListener("click", () => {

    const isOpen = !memberDropdown.hidden;

    memberDropdown.hidden = isOpen;

    memberTrigger.setAttribute(
        "aria-expanded",
        String(!isOpen)
    );

});

// ==============================
// 點擊選單外部時自動收起
// ==============================
document.addEventListener("click", (event) => {

    if (!memberMenu.contains(event.target)) {
        closeMemberDropdown();
    }

});

// ==============================
// 按下 Esc 收起會員選單
// ==============================
document.addEventListener("keydown", (event) => {

    if (event.key === "Escape" && !memberDropdown.hidden) {

        closeMemberDropdown();

        // 將焦點移回會員按鈕
        memberTrigger.focus();

    }

});

// ==============================
// 會員登出
// ==============================
memberLogout.addEventListener("click", () => {

    // 移除 JWT
    sessionStorage.removeItem("tutorlink_token");

    // 恢復未登入畫面
    updateMemberUI();

    // 通知其他頁面功能：會員已登出
    window.dispatchEvent(new Event("tutorlink:logout"));

    // 顯示登出成功通知
    showAuthToast("已成功登出", "期待下次再見！");

});

// ==============================
// Delete Account Modal 刪除帳號確認視窗
// ==============================
// 取得相關元素
const memberDelete = document.getElementById("member-delete");
const deleteAccountModal = document.getElementById("delete-account-modal");
const deleteAccountCancel = document.getElementById("delete-account-cancel");
const deleteAccountConfirm = document.getElementById("delete-account-confirm");
const deleteAccountOverlay = deleteAccountModal.querySelector(".delete-account-overlay");

// 記錄開啟視窗前的焦點
let deleteAccountPreviousFocus = null;

// 開啟刪除帳號確認視窗
function openDeleteAccountModal() {
    deleteAccountPreviousFocus = document.activeElement;

    // 收起會員下拉選單
    closeMemberDropdown();

    // 顯示確認視窗
    deleteAccountModal.hidden = false;

    // 預設將焦點放在安全的「取消」按鈕
    deleteAccountCancel.focus();
}

// 關閉刪除帳號確認視窗
function closeDeleteAccountModal() {
    // 刪除進行中，不允許關閉視窗
    if (deleteAccountConfirm.disabled) {
        return;
    }

    deleteAccountModal.hidden = true;

    // 因為下拉選單已收起，將焦點還給會員選單按鈕
    if (!memberMenu.hidden) {
        memberTrigger.focus();
    } else {
        deleteAccountPreviousFocus?.focus();
    }
}

// 點擊「刪除帳號」開啟視窗
memberDelete.addEventListener("click", openDeleteAccountModal);

// 點擊「取消」關閉視窗
deleteAccountCancel.addEventListener("click", closeDeleteAccountModal);

// 點擊背景遮罩關閉視窗
deleteAccountOverlay.addEventListener("click", closeDeleteAccountModal);

// 按 Escape 關閉視窗
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !deleteAccountModal.hidden) {
        event.preventDefault();
        closeDeleteAccountModal();
    }
});

// 視窗開啟時，限制 Tab 焦點留在視窗內
deleteAccountModal.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") {
        return;
    }

    const focusableElements = [
        deleteAccountCancel,
        deleteAccountConfirm
    ].filter((button) => !button.disabled);

    if (focusableElements.length === 0) {
        event.preventDefault();
        return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
    }
});

// ==============================
// 確認刪除會員帳號
// ==============================
deleteAccountConfirm.addEventListener("click", async () => {

    // 防止重複送出
    if (deleteAccountConfirm.disabled) {
        return;
    }

    // 取得目前登入的 JWT
    const token = sessionStorage.getItem("tutorlink_token");

    if (!token) {
        closeDeleteAccountModal();
        showAuthToast("請重新登入", "登入狀態已失效，請重新登入後再試");
        return;
    }

    // 刪除期間禁止重複操作
    deleteAccountConfirm.disabled = true;
    deleteAccountCancel.disabled = true;
    deleteAccountConfirm.textContent = "刪除中...";

    try {
        const response = await fetch("/api/auth/me", {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                sessionStorage.removeItem("tutorlink_token");
                updateMemberUI();
                window.dispatchEvent(new Event("tutorlink:logout"));
                deleteAccountConfirm.disabled = false;
                closeDeleteAccountModal();
                showAuthToast("登入已失效", "請重新登入後再試");
            } else {
                showAuthToast("刪除失敗", "帳號尚未刪除，請稍後再試");
            }
            return;
        }

        // 刪除成功後，清除本機登入狀態
        sessionStorage.removeItem("tutorlink_token");
        updateMemberUI();

        // 通知其他頁面功能：會員已登出
        window.dispatchEvent(new Event("tutorlink:logout"));

        // 關閉確認視窗
        deleteAccountConfirm.disabled = false;
        closeDeleteAccountModal();

        // 返回首頁
        window.location.replace("/");

    } catch (error) {
        console.error("刪除會員帳號發生錯誤：", error);
        showAuthToast("刪除結果未確認", "請重新整理並確認帳號狀態，避免重複操作");

    } finally {
        deleteAccountConfirm.disabled = false;
        deleteAccountCancel.disabled = false;
        deleteAccountConfirm.textContent = "確認刪除帳號";
    }
});

// ==============================
// 頁面載入時恢復會員狀態
// ==============================
async function initializeAuth() {

    try {

        // 等待 FastAPI 確認目前的會員身分
        await loadCurrentUser();

    } finally {

        // 無論成功或失敗，都結束載入狀態
        document.body.classList.add("auth-ready");

    }

}

// 頁面載入時執行
initializeAuth();
