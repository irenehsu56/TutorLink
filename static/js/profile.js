if (window.lucide) {lucide.createIcons();}

// ==============================
document.addEventListener("DOMContentLoaded", () => {

    // 1. 取得 HTML 元素
    // 未登入提示區域與會員資料區域
    const loginRequired = document.getElementById("profile-login-required");
    const profileContent = document.getElementById("profile-content");

    // 會員基本資料：預設以純文字顯示
    const displayName = document.getElementById("profile-display-name");
    const displayEmail = document.getElementById("profile-display-email");

    // 修改姓名相關元素
    const nameForm = document.getElementById("profile-info-form");
    const nameInput = document.getElementById("profile-name");
    const nameEdit = document.getElementById("profile-name-edit");
    const nameCancel = document.getElementById("profile-name-cancel");
    const nameSave = document.getElementById("profile-save-button");

    // 修改密碼相關元素
    const passwordForm = document.getElementById("profile-password-form");
    const passwordToggle = document.getElementById("profile-password-toggle");
    const passwordCancel = document.getElementById("profile-password-cancel");

    // 三個密碼輸入欄位
    const currentPassword = document.getElementById("profile-current-password");
    const newPassword = document.getElementById("profile-new-password");
    const confirmPassword = document.getElementById("profile-confirm-password");

    // 修改密碼表單內的提示訊息
    const passwordMessage = document.getElementById("profile-password-message");

    // 顯示密碼表單提示
    function showPasswordMessage(message, type = "error") {
        passwordMessage.textContent = message;
        passwordMessage.classList.remove("is-error", "is-success");
        passwordMessage.classList.add(
            type === "success" ? "is-success" : "is-error"
        );
        passwordMessage.hidden = false;
    }

    // 清除密碼表單提示
    function clearPasswordMessage() {
        passwordMessage.textContent = "";
        passwordMessage.classList.remove("is-error", "is-success");
        passwordMessage.hidden = true;
    }

    // 會員頭貼相關元素
    const avatar = document.getElementById("profile-avatar");
    const photoInput = document.getElementById("profile-photo-input");
    const photoButton = document.getElementById("profile-photo-button");

    // Toast 提示訊息相關元素
    const profileToast = document.getElementById("profile-toast");
    const profileToastMessage = document.getElementById("profile-toast-message");

    // 儲存提示訊息的計時器
    let toastTimer = null;

    // 2. 頁面狀態變數
    // 儲存目前登入會員的資料
    // 登出時會清空，避免顯示前一個帳號的資料
    let currentUser = null;

    // 用來辨識最新一次會員資料查詢
    // 避免快速登入／登出時，舊請求覆蓋新畫面
    let profileRequestId = 0;

    // 儲存本機頭貼預覽網址
    // 使用完畢後需要釋放，避免佔用記憶體
    let avatarPreviewUrl = null;

    // 顯示個人資料操作提示
    // type 可設定 success 或 error
    function showToast(message, type = "success") {

        // 清除上一則提示的計時器
        if (toastTimer !== null) {
            clearTimeout(toastTimer);
            toastTimer = null;
        }

        // 設定提示文字
        profileToastMessage.textContent = message;

        // 清除上一則提示的狀態
        profileToast.classList.remove("is-success", "is-error");

        // 套用成功或錯誤樣式
        profileToast.classList.add(
            type === "error" ? "is-error" : "is-success"
        );

        // 顯示提示
        profileToast.hidden = false;

        // 3 秒後自動隱藏
        toastTimer = setTimeout(() => {
            profileToast.hidden = true;
            toastTimer = null;
        }, 3000);
    }

    // 3. 共用工具函式
    // 取得目前會員的 JWT，使用 sessionStorage 儲存登入 Token。
    function getToken() {
        return sessionStorage.getItem("tutorlink_token");
    }

    // 重新初始化 Lucide 圖示
    // 動態新增 HTML 圖示時，需要重新執行。
    function refreshIcons() {
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    // 釋放舊的本機頭貼預覽網址
    function revokeAvatarPreview() {
        if (avatarPreviewUrl) {
            URL.revokeObjectURL(avatarPreviewUrl);
            avatarPreviewUrl = null;
        }
    }

    // 將頭貼恢復為預設會員圖示
    function resetAvatar() {
        revokeAvatarPreview();

        // 清除原本的圖片或圖示
        avatar.replaceChildren();

        // 建立預設會員圖示
        const icon = document.createElement("i");
        icon.setAttribute("data-lucide", "user-round");

        avatar.appendChild(icon);

        refreshIcons();
    }

    // 顯示會員頭貼
    function showAvatar(url) {
        if (!url) {
            resetAvatar();
            return;
        }

        revokeAvatarPreview();

        const image = document.createElement("img");

        image.alt = "會員頭貼";
        image.src = url;

        // 圖片失效時，恢復預設圖示
        image.onerror = () => {
            if (avatar.contains(image)) {
                resetAvatar();
            }
        };

        avatar.replaceChildren(image);
    }

    // 4. 姓名與密碼表單的顯示控制
    // 關閉姓名編輯模式
    function closeNameEditor() {
        nameForm.hidden = true;
        displayName.hidden = false;
        nameEdit.hidden = false;
    }

    // 關閉修改密碼表單
    function closePasswordEditor() {
        passwordForm.reset();

        clearPasswordMessage();

        passwordForm.hidden = true;
        passwordToggle.hidden = false;

        // 更新無障礙屬性
        passwordToggle.setAttribute("aria-expanded", "false");
    }


    // 5. 未登入與已登入畫面切換
    // 顯示未登入提示
    function showLoginRequired() {

        // 使之前尚未完成的會員資料查詢失效
        profileRequestId++;

        // 清空目前會員
        currentUser = null;

        // 登出時清除上一位會員的提示訊息
        if (toastTimer !== null) {
            clearTimeout(toastTimer);
            toastTimer = null;
        }

        profileToast.hidden = true;
        profileToastMessage.textContent = "";

        // 切換畫面
        loginRequired.hidden = false;
        profileContent.hidden = true;

        // 套用共用未登入頁面樣式
        document.body.classList.add("member-login-required");

        // 清除上一位會員的資料
        displayName.textContent = "";
        displayEmail.textContent = "";
        nameInput.value = "";

        // 重設表單狀態
        closeNameEditor();
        closePasswordEditor();

        // 重設會員頭貼
        resetAvatar();
    }

    // 顯示目前會員資料
    function showProfile(user) {

        // 儲存目前會員資料
        currentUser = user;

        // 更新姓名與 Email
        displayName.textContent = user.name || "";
        displayEmail.textContent = user.email || "";

        // 預先填入姓名編輯欄位
        nameInput.value = user.name || "";

        // 每次載入會員時，恢復預設檢視模式
        closeNameEditor();
        closePasswordEditor();

        // 顯示會員頭貼
        // 若後端沒有 photo_url，則顯示預設圖示
        showAvatar(user.photo_url || null);

        // 切換成已登入畫面
        loginRequired.hidden = true;
        profileContent.hidden = false;

        document.body.classList.remove("member-login-required");

        refreshIcons();
    }

    // 6. 從後端取得目前會員資料
    // GET /api/auth/me
    async function loadProfile() {

        const token = getToken();

        // 記錄這次請求的編號
        const requestId = ++profileRequestId;

        // 沒有 Token，代表尚未登入
        if (!token) {
            showLoginRequired();
            return;
        }

        try {

            const response = await fetch("/api/auth/me", {
                method: "GET",
                headers: {
                    Authorization: `Bearer ${token}`
                },
                cache: "no-store"
            });

            if (!response.ok) {
                throw new Error("無法取得會員資料");
            }

            const data = await response.json();

            // 如果請求期間已切換帳號或登出，
            // 就忽略這次舊請求的結果
            if (
                token !== getToken() ||
                requestId !== profileRequestId
            ) {
                return;
            }

            // 確認後端有回傳會員資料
            if (!data.user) {
                throw new Error("會員資料不存在");
            }

            // 顯示會員資料
            showProfile(data.user);

        } catch (error) {

            // 舊請求失敗時，不影響新帳號畫面
            if (
                token !== getToken() ||
                requestId !== profileRequestId
            ) {
                return;
            }

            console.error("載入會員資料失敗：", error);

            showLoginRequired();
        }
    }

    // 7. 點擊「修改姓名」
    // 預設姓名是純文字。
    nameEdit.addEventListener("click", () => {

        if (!currentUser) return;

        // 每次編輯都使用目前會員的最新姓名
        nameInput.value = currentUser.name || "";

        displayName.hidden = true;
        nameEdit.hidden = true;
        nameForm.hidden = false;

        // 自動將游標移到姓名輸入框
        nameInput.focus();
    });

    // 取消修改姓名
    nameCancel.addEventListener("click", () => {
        closeNameEditor();
    });

    // 8. 儲存會員姓名
    // PATCH /api/auth/me
    nameForm.addEventListener("submit", async (event) => {

        // 阻止表單預設重新整理頁面
        event.preventDefault();

        if (!currentUser) return;

        const token = getToken();

        // 記錄送出時的會員 ID
        const userId = currentUser.id;

        // 移除姓名前後空白
        const newName = nameInput.value.trim();

        // 姓名不可為空
        if (!newName) {
            showToast("會員姓名不可為空白");
            return;
        }

        // 避免重複點擊儲存按鈕
        nameSave.disabled = true;

        try {

            const response = await fetch("/api/auth/me", {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    name: newName,

                    // Email 不開放修改，送回原本的值
                    email: currentUser.email
                })
            });

            const data = await response.json();

            // 如果送出期間切換帳號，就不更新畫面
            if (
                token !== getToken() ||
                currentUser?.id !== userId
            ) {
                return;
            }

            // 後端回傳錯誤
            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "修改姓名失敗"
                );
            }

            // 更新目前會員資料
            currentUser = data.user;

            // 更新頁面姓名
            displayName.textContent = data.user.name;
            nameInput.value = data.user.name;

            // 恢復純文字顯示
            closeNameEditor();

            // 通知 auth.js 重新載入會員資料，
            // 讓 Header 顯示最新姓名
            window.dispatchEvent(
                new Event("tutorlink:profile-updated")
            );

            showToast("會員姓名修改成功");

        } catch (error) {

            if (token === getToken() && currentUser?.id === userId) {
                showToast(error.message || "修改姓名失敗");
            }

        } finally {

            // 恢復儲存按鈕
            nameSave.disabled = false;
        }
    });

    // 9. 展開修改密碼表單
    // 點擊「修改密碼」後：隱藏修改密碼按鈕
    passwordToggle.addEventListener("click", () => {

        if (!currentUser) return;

        passwordToggle.hidden = true;
        passwordForm.hidden = false;

        passwordToggle.setAttribute("aria-expanded", "true");

        // 自動將游標移到目前密碼欄位
        currentPassword.focus();
    });

    // 取消修改密碼
    passwordCancel.addEventListener("click", () => {
        closePasswordEditor();
    });

    // 10. 修改密碼表單驗證與後端 API 串接
    // 重新輸入密碼時，清除先前的提示
    [currentPassword, newPassword, confirmPassword].forEach((input) => {
        input.addEventListener("input", () => {
            clearPasswordMessage();
        });
    });

    // PATCH /api/auth/me/password
    passwordForm.addEventListener("submit", async (event) => {

        // 阻止表單重新整理頁面
        event.preventDefault();

        if (!currentUser) return;

        const token = getToken();
        if (!token) return;

        // 記錄送出時的會員 ID，避免切換帳號後更新錯誤畫面
        const userId = currentUser.id;

        // 取得密碼欄位內容
        const currentPasswordValue = currentPassword.value;
        const newPasswordValue = newPassword.value;
        const confirmPasswordValue = confirmPassword.value;

        // 確認所有欄位都有填寫
        if (
            !currentPasswordValue ||
            !newPasswordValue ||
            !confirmPasswordValue
        ) {
            showPasswordMessage("請填寫所有密碼欄位", "error");
            return;
        }

        // 新密碼長度驗證
        if (
            newPasswordValue.length < 8 ||
            newPasswordValue.length > 128
        ) {
            showPasswordMessage("新密碼長度必須為 8～128 個字元", "error");
            return;
        }

        // 新密碼與確認密碼必須一致
        if (newPasswordValue !== confirmPasswordValue) {
            showPasswordMessage("新密碼與確認新密碼不一致", "error");
            return;
        }

        // 新密碼不能與目前密碼相同
        if (newPasswordValue === currentPasswordValue) {
            showPasswordMessage("新密碼不可與目前密碼相同", "error");
            return;
        }

        // 取得更新密碼按鈕
        const passwordSave = document.getElementById(
            "profile-password-button"
        );

        // 防止重複送出
        passwordSave.disabled = true;
        passwordSave.textContent = "更新中...";

        try {

            // 呼叫修改密碼 API
            const response = await fetch("/api/auth/me/password", {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    current_password: currentPasswordValue,
                    new_password: newPasswordValue,
                    confirm_password: confirmPasswordValue
                })
            });

            const data = await response.json();

            // 如果送出期間已登出或切換帳號，不更新舊會員畫面
            if (
                token !== getToken() ||
                currentUser?.id !== userId
            ) {
                return;
            }

            // 處理後端錯誤訊息
            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "修改密碼失敗"
                );
            }

            // 修改成功後，清空密碼欄位並收合表單
            closePasswordEditor();

            // 顯示成功通知
            showToast("密碼修改成功");

        } catch (error) {

            // 只在原帳號仍登入時顯示錯誤
            if (
                token === getToken() &&
                currentUser?.id === userId
            ) {
                showPasswordMessage(
                    error.message || "修改密碼失敗，請稍後再試",
                    "error"
                );
            }

        } finally {

            // 恢復按鈕狀態
            passwordSave.disabled = false;
            passwordSave.textContent = "更新密碼";
        }
    });

    // 11. 點擊「更換頭貼」
    // 點擊自訂按鈕時，觸發隱藏的檔案選擇欄位
    photoButton.addEventListener("click", () => {

        if (!currentUser) return;

        photoInput.click();
    });

    // 12. 上傳會員頭貼
    // POST /api/auth/me/photo
    photoInput.addEventListener("change", async () => {

        // 取得使用者選擇的檔案
        const file = photoInput.files?.[0];

        if (!file || !currentUser) return;

        // 允許的圖片格式
        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        // 檢查檔案格式
        if (!allowedTypes.includes(file.type)) {
            showToast("只允許上傳 JPG、PNG 或 WebP 圖片");
            photoInput.value = "";
            return;
        }

        // 檢查檔案大小：5 MB
        if (file.size > 5 * 1024 * 1024) {
            showToast("照片不可超過 5 MB");
            photoInput.value = "";
            return;
        }

        const token = getToken();
        const userId = currentUser.id;

        // 建立 multipart/form-data
        const formData = new FormData();

        // 欄位名稱 photo 必須與 FastAPI 參數一致
        formData.append("photo", file);

        // 上傳期間禁止重複點擊
        photoButton.disabled = true;

        try {

            const response = await fetch("/api/auth/me/photo", {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`
                },
                body: formData
            });

            const data = await response.json();

            // 上傳期間若切換帳號，不顯示舊帳號頭貼
            if (
                token !== getToken() ||
                currentUser?.id !== userId
            ) {
                return;
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "上傳頭貼失敗"
                );
            }

            // 釋放舊的本機預覽網址
            revokeAvatarPreview();

            // 建立新頭貼的本機預覽網址
            avatarPreviewUrl = URL.createObjectURL(file);

            const image = document.createElement("img");

            image.src = avatarPreviewUrl;
            image.alt = "會員頭貼";

            // 顯示新頭貼
            avatar.replaceChildren(image);

            // 通知 auth.js 重新取得會員資料
            // 同步更新 Header 的會員頭貼
            window.dispatchEvent(
                new Event("tutorlink:profile-updated")
            );

            showToast("會員頭貼上傳成功");

        } catch (error) {

            if (token === getToken() && currentUser?.id === userId) {
                showToast(error.message || "上傳頭貼失敗");
            }

        } finally {

            // 恢復按鈕與清除檔案選擇
            photoButton.disabled = false;
            photoInput.value = "";
        }
    });

    // 13. 會員登入／登出事件同步
    // 會員登入：重新取得目前帳號的資料
    window.addEventListener("tutorlink:login", loadProfile);

    // 會員登出：立即清除畫面上的會員資料，避免殘留上一位會員的姓名與頭貼。
    window.addEventListener("tutorlink:logout", showLoginRequired);

    // 14. 頁面初始化
    // 載入目前會員資料
    loadProfile();

    // 初始化 Lucide 圖示
    refreshIcons();

});
