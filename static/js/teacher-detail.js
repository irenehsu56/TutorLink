if (window.lucide) {lucide.createIcons();}

// ==============================
// 教學科目：英文代碼轉中文
// ==============================
const subjectNameMap = {
    math: "數學",
    english: "英文",
    chinese: "國文",
    science: "自然",
    social: "社會",
    art: "美術",
    music: "音樂",
    other: "其他"
};

// ==============================
// 教學年級：英文代碼轉中文
// ==============================
const gradeNameMap = {
    elementary: "國小",
    junior: "國中",
    senior: "高中"
};

// ==============================
// 判斷目前是公開老師頁，還是老師自己的個人頁
// ==============================
const isMyTeacherProfilePage =
    window.location.pathname === "/my-teacher-profile.html";

// 公開老師頁才需要從網址取得 ID
const urlParams = new URLSearchParams(window.location.search);
const teacherId = urlParams.get("id");

// ==============================
// 聯絡老師：建立或取得對話
// ==============================
const contactTeacherButton = document.getElementById("detail-contact-button");

if (contactTeacherButton && !isMyTeacherProfilePage) {
    contactTeacherButton.addEventListener("click", async () => {

        // 未登入時開啟登入視窗
        const token = sessionStorage.getItem("tutorlink_token");

        if (!token) {
            openAuthModal("login");
            return;
        }

        // 確認老師 ID 有效
        if (!teacherId || !/^[1-9]\d*$/.test(teacherId)) return;

        // 防止重複點擊
        if (contactTeacherButton.disabled) return;
        contactTeacherButton.disabled = true;

        try {
            const response = await fetch(
                `/api/conversations/teacher/${teacherId}`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    }
                }
            );

            if (!response.ok) {
                throw new Error("無法開啟與老師的對話");
            }

            const data = await response.json();

            // 會員已切換時，不使用舊請求結果
            if (sessionStorage.getItem("tutorlink_token") !== token) return;

            // 跳轉到私訊頁，並指定要開啟的對話
            window.location.href =
                `/messages.html?conversation_id=${encodeURIComponent(data.conversation_id)}`;

        } catch (error) {
            if (sessionStorage.getItem("tutorlink_token") !== token) return;

            console.error("聯絡老師失敗：", error);
            alert("目前無法聯絡老師，請稍後再試。");

        } finally {
            contactTeacherButton.disabled = false;
        }
    });
}

// ==============================
// 老師身分查詢控制
// ==============================

// 目前正在執行的身分查詢
let ownershipController = null;

// 每次查詢都會增加的序號
let ownershipRequestId = 0;

// ==============================
// 老師個人頁：未登入提示
// ==============================
function showTeacherLoginNotice() {

    // 使用全站共用的未登入頁面樣式
    document.body.classList.add("member-login-required");
    document.body.classList.remove("teacher-login-required");

    // 隱藏老師資料，避免顯示載入中或舊資料
    document.querySelectorAll(
        ".teacher-detail-page .detail-card"
    ).forEach(function (card) {
        card.hidden = true;
    });

    // 避免重複建立提示
    if (document.getElementById("teacher-login-notice")) {
        return;
    }

    const notice = document.createElement("div");
    notice.id = "teacher-login-notice";
    notice.className = "member-login-screen";

    notice.innerHTML = `
        <div class="member-login-card">

            <div class="member-login-icon">
                <i data-lucide="lock-keyhole"></i>
            </div>

            <h2>請先登入會員</h2>

            <p>
                登入 TutorLink 後，即可查看與管理<br>
                你的家教個人資料！
            </p>

            <button type="button" id="teacher-profile-login-button">
                立即登入
            </button>

        </div>
    `;

    document.body.appendChild(notice);

    if (window.lucide) {
        lucide.createIcons();
    }

    document.getElementById("teacher-profile-login-button")
        .addEventListener("click", function () {
            openAuthModal("login");
        });
}

// ==============================
// 老師個人頁：尚未建立老師資料
// ==============================
function showTeacherEmptyProfile() {

    // 隱藏原本的老師資料卡片
    detailCards.forEach(function (card) {
        card.hidden = true;
    });

    const main = document.querySelector(".teacher-detail-page");

    // 避免重複建立
    if (document.getElementById("teacher-empty-profile")) {
        return;
    }

    const emptyProfile = document.createElement("div");
    emptyProfile.id = "teacher-empty-profile";
    emptyProfile.className = "teacher-empty-profile";

    emptyProfile.innerHTML = `
        <div class="teacher-empty-card">

            <div class="teacher-empty-icon">
                <i data-lucide="graduation-cap"></i>
            </div>

            <h2>尚未建立老師資料</h2>

            <p>
                建立你的個人教學檔案，讓更多學生看見你的專長，
                開啟家教之旅！
            </p>

            <a href="/become-teacher.html"
               class="teacher-empty-button">
                <i data-lucide="plus-circle"></i>
                立即建立老師資料
            </a>

        </div>
    `;

    main.appendChild(emptyProfile);

    lucide.createIcons();
}

// ==============================
// 取得老師詳細資料
// ==============================
async function loadTeacherDetail() {

    // 公開老師頁必須提供有效的老師 ID
    if (
        !isMyTeacherProfilePage &&
        (!teacherId || !/^[1-9]\d*$/.test(teacherId))
    ) {
        showTeacherError("老師資料網址不正確");
        return;
    }

    try {
        // 老師個人頁使用登入憑證查詢自己的資料
        const token = sessionStorage.getItem("tutorlink_token");

        if (isMyTeacherProfilePage && !token) {
            showTeacherLoginNotice();
            return;
        }

        // 根據頁面類型決定 API
        const apiUrl = isMyTeacherProfilePage
            ? "/api/teachers/me"
            : `/api/teachers/${teacherId}`;

        const fetchOptions = isMyTeacherProfilePage
            ? {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
            : {};

        const response = await fetch(apiUrl, fetchOptions);

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                if (isMyTeacherProfilePage) {
                    showTeacherLoginNotice();
                    return;
                }

                throw new Error("登入已失效，請重新登入");
            }

            if (response.status === 404) {
                // 已登入，但尚未建立老師資料
                if (isMyTeacherProfilePage) {
                    showTeacherEmptyProfile();
                    return;
                }

                throw new Error("找不到這位老師");
            }

            throw new Error("老師資料載入失敗");
        }

        const data = await response.json();

        // 將資料顯示在頁面
        renderTeacherDetail(data.teacher);

        // 公開老師詳細頁：查詢收藏狀態並綁定點擊事件
        if (!isMyTeacherProfilePage) {
            loadFavoriteStatus(data.teacher.id);

            // 載入學生課後評價
            loadTeacherReviews(data.teacher.id);

            const favoriteButton = document.getElementById("detail-favorite-button");

            if (favoriteButton) {
                favoriteButton.onclick = function () {
                    toggleTeacherFavorite(data.teacher.id);
                };
            }
        }

    } catch (error) {
        console.error("載入老師詳細資料失敗：", error);
        showTeacherError(error.message);
    }
}

// ==============================
// 顯示老師詳細資料
// ==============================

// 目前老師開放的授課時段
let currentTeacherAvailability = [];

// 目前老師的每小時收費
let currentTeacherHourlyRate = 0;

function renderTeacherDetail(teacher) {

    // 姓名
    document.getElementById("detail-name").textContent =
        teacher.name || "未提供姓名";

    // 更新瀏覽器分頁標題
    document.title = `${teacher.name}｜TutorLink 老師詳細介紹`;

    // 性別
    const genderMap = {
        male: "男",
        female: "女",
        other: "其他"
    };

    const gender = genderMap[teacher.gender] ??
        teacher.gender ?? "未提供";

    setIconText("detail-gender", "user-round", gender);

    // 學歷
    setIconText(
        "detail-education",
        "graduation-cap",
        teacher.education || "未提供學歷"
    );

    // 教學經驗
    const experience = teacher.experience ?? 0;

    setIconText(
        "detail-experience",
        "award",
        `${experience} 年教學經驗`
    );

    document.getElementById("detail-teaching-experience").textContent =
        `${experience} 年`;

    // 每小時收費
    const hourlyRate = Number(
        teacher.hourlyRate ?? teacher.hourly_rate ?? 0
    );

    // 儲存老師收費，供預約表單使用
    currentTeacherHourlyRate = hourlyRate;

    console.log("老師每小時收費：", currentTeacherHourlyRate);

    const formattedPrice = Number(hourlyRate).toLocaleString("zh-TW");

    setIconText(
        "detail-hourly-rate",
        "coins",
        `NT$ ${formattedPrice} / 小時`
    );

    document.getElementById("detail-teaching-price").textContent =
        `NT$ ${formattedPrice}`;

    // 頭貼
    renderTeacherAvatar(teacher);

    // 教學科目及年級
    renderTeacherTags(teacher);

    // 預約視窗：載入老師實際教授的科目
    if (!isMyTeacherProfilePage) {
        renderBookingSubjects(teacher.subjects || []);
    }

    // 授課地區
    renderTeacherLocations(teacher.locations || []);

    // 可授課時段
    currentTeacherAvailability = teacher.availability || [];
    renderTeacherSchedule(currentTeacherAvailability);

    // 自我介紹
    document.getElementById("detail-intro").textContent =
        teacher.intro || "這位老師尚未填寫自我介紹。";

    // 根據目前頁面類型，決定顯示哪些操作按鈕
    if (isMyTeacherProfilePage) {

        // 老師自己的個人頁：顯示編輯、刪除按鈕
        document.getElementById("detail-edit-button").hidden = false;
        document.getElementById("detail-delete-button").hidden = false;

        // 隱藏聯絡、收藏按鈕
        document.getElementById("detail-contact-button").hidden = true;
        document.getElementById("detail-favorite-button").hidden = true;

    } else {

        // 公開老師詳細頁：維持原本的身分確認機制
        checkTeacherOwnership(teacher.id);
    }

    // 將動態新增的 Icon 轉換為 SVG
    lucide.createIcons();

    // 資料載入完成後，顯示老師詳細資料卡片
    detailCards.forEach(function (card) {
        card.hidden = false;
    });
}

// ==============================
// 確認目前登入者是否為老師本人
// ==============================
async function checkTeacherOwnership(teacherId) {

    const editButton = document.getElementById(
        "detail-edit-button"
    );

    const deleteButton = document.getElementById(
        "detail-delete-button"
    );

    const contactButton = document.getElementById(
        "detail-contact-button"
    );

    const favoriteButton = document.getElementById(
        "detail-favorite-button"
    );

    // 預約上課按鈕區域
    const bookingActions = document.getElementById(
        "detail-booking-actions"
    );

    // 身分確認期間先隱藏
    if (bookingActions) {
        bookingActions.hidden = true;
    }

    // 每次查詢都產生新的序號
    const requestId = ++ownershipRequestId;

    // 取消前一次尚未完成的身分查詢
    if (ownershipController) {
        ownershipController.abort();
    }

    // 建立這次查詢的控制器
    const controller = new AbortController();
    ownershipController = controller;

    // 預設顯示一般使用者按鈕
    editButton.hidden = true;
    deleteButton.hidden = true;
    contactButton.hidden = false;

    // 取得目前登入憑證
    const token = sessionStorage.getItem("tutorlink_token");

    // 只有登入會員才顯示收藏按鈕
    favoriteButton.hidden = !token;
    favoriteButton.disabled = true;

    // 未登入：可以看到預約按鈕，點擊後提示登入
    if (!token) {
        if (bookingActions) {
            bookingActions.hidden =
                currentTeacherAvailability.length === 0;
        }

        ownershipController = null;
        return;
    }

    try {

        // 查詢目前登入會員的老師資料
        const response = await fetch("/api/teachers/me", {
            headers: {
                "Authorization": `Bearer ${token}`
            },
            signal: controller.signal
        });

        // API 查詢失敗
        if (!response.ok) {
            // 404：目前會員沒有老師資料，可視為一般學生
            if (
                response.status === 404 &&
                requestId === ownershipRequestId &&
                !controller.signal.aborted &&
                sessionStorage.getItem("tutorlink_token") === token
            ) {
                if (bookingActions) {
                    bookingActions.hidden =
                        currentTeacherAvailability.length === 0;
                }
            }

            return;
        }

        const data = await response.json();

        // 確認查詢結果仍然有效
        // 不是最新查詢，就不更新畫面
        if (requestId !== ownershipRequestId) {
            return;
        }

        // 查詢已被取消，就不更新畫面
        if (controller.signal.aborted) {
            return;
        }

        // 登入憑證已改變，就不更新畫面
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        // 確認目前登入者是否為這位老師本人
        const isOwner =
            data.teacher &&
            Number(data.teacher.id) === Number(teacherId);

        // 不是老師本人且有開放時段，才顯示預約按鈕
        if (bookingActions) {
            bookingActions.hidden =
                Boolean(isOwner) ||
                currentTeacherAvailability.length === 0;
        }

        if (isOwner) {

            // 老師本人：顯示編輯與刪除老師資料
            editButton.hidden = false;
            deleteButton.hidden = false;

            // 隱藏一般使用者操作按鈕
            contactButton.hidden = true;
            favoriteButton.hidden = true;
        }

    } catch (error) {

        // 主動取消的舊查詢，不視為錯誤
        if (error.name !== "AbortError") {
            console.error("確認老師身分失敗：", error);
        }

    } finally {

        // 只有最新查詢才能清除控制器
        if (requestId === ownershipRequestId) {
            ownershipController = null;
        }
    }
}

// ==============================
// 會員登入或登出後，更新老師頁面按鈕
// ==============================
function refreshTeacherDetailActions() {

    // 老師自己的個人頁：登入狀態改變後重新載入頁面
    if (isMyTeacherProfilePage) {
        window.location.reload();
        return;
    }

    // 公開老師詳細頁：確認老師 ID
    if (!teacherId || !/^[1-9]\d*$/.test(teacherId)) {
        return;
    }

    // 先隱藏收藏按鈕，避免顯示上一位會員的收藏狀態
    const favoriteButton = document.getElementById("detail-favorite-button");
    favoriteButton.hidden = true;
    favoriteButton.disabled = true;

    // 重新確認目前會員是否為老師本人
    checkTeacherOwnership(teacherId);

    // 重新讀取目前會員的收藏狀態
    loadFavoriteStatus(teacherId);

    // 登入、登出或切換會員後，重新載入學生評價
    loadTeacherReviews(teacherId);
}

// ==============================
// 更新含 Icon 的文字欄位
// ==============================
function setIconText(elementId, iconName, value) {

    const element = document.getElementById(elementId);

    // 清空原本測試資料
    element.replaceChildren();

    // 新增 Icon
    const icon = document.createElement("i");
    icon.setAttribute("data-lucide", iconName);

    // 新增文字
    const text = document.createTextNode(` ${value}`);

    element.appendChild(icon);
    element.appendChild(text);
}

// ==============================
// 顯示老師頭貼
// ==============================
function renderTeacherAvatar(teacher) {

    const avatar = document.getElementById("detail-avatar");

    avatar.replaceChildren();

    // 根據老師性別設定預設頭像顏色
    avatar.classList.remove("male", "female");

    if (teacher.gender === "男" || teacher.gender === "male") {
        avatar.classList.add("male");
    } else if (teacher.gender === "女" || teacher.gender === "female") {
        avatar.classList.add("female");
    }

    // 老師有上傳頭貼
    if (teacher.photo_url) {

        const image = document.createElement("img");

        image.src = teacher.photo_url;
        image.alt = `${teacher.name}的頭貼`;
        image.referrerPolicy = "no-referrer";

        // 照片載入失敗時，顯示預設人物圖示
        image.onerror = function () {
            avatar.replaceChildren();

            const icon = document.createElement("i");
            icon.setAttribute("data-lucide", "user-round");

            avatar.appendChild(icon);
            lucide.createIcons();
        };

        avatar.appendChild(image);

    } else {

        // 沒有頭貼時，使用預設人物 Icon
        const icon = document.createElement("i");
        icon.setAttribute("data-lucide", "user-round");

        avatar.appendChild(icon);
    }
}

// ==============================
// 查詢老師收藏狀態
// ==============================
async function loadFavoriteStatus(teacherId) {
    const favoriteButton = document.getElementById("detail-favorite-button");
    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入時，隱藏收藏按鈕並清除舊狀態
    if (!token) {
        favoriteButton.hidden = true;
        favoriteButton.disabled = true;
        favoriteButton.classList.remove("is-favorited");
        favoriteButton.innerHTML = `
            <i data-lucide="heart"></i>
            收藏老師
        `;
        lucide.createIcons();
        return;
    }

    try {
        const response = await fetch(`/api/favorites/${teacherId}/status`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("查詢收藏狀態失敗");
        }

        const data = await response.json();

        // 登入憑證已改變時，不使用舊的查詢結果
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        // 根據收藏狀態更新按鈕
        favoriteButton.classList.toggle("is-favorited", data.is_favorited);

        favoriteButton.innerHTML = `
            <i data-lucide="heart"></i>
            ${data.is_favorited ? "已收藏" : "收藏老師"}
        `;

        lucide.createIcons();

        // 收藏狀態確認完成後，才允許點擊
        favoriteButton.disabled = false;

    } catch (error) {
        console.error("讀取收藏狀態失敗：", error);
    }
}

// ==============================
// 收藏老師／取消收藏老師
// ==============================
async function toggleTeacherFavorite(teacherId) {
    const favoriteButton = document.getElementById("detail-favorite-button");
    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入時提示登入
    if (!token) {
        alert("請先登入會員，才能收藏老師");
        return;
    }

    // 根據目前按鈕狀態，決定收藏或取消收藏
    const isFavorited = favoriteButton.classList.contains("is-favorited");
    const method = isFavorited ? "DELETE" : "POST";

    // 避免重複點擊
    favoriteButton.disabled = true;

    try {
        const response = await fetch(`/api/favorites/${teacherId}`, {
            method: method,
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "收藏操作失敗");
        }

        // 操作成功後更新收藏狀態
        const newIsFavorited = !isFavorited;

        favoriteButton.classList.toggle("is-favorited", newIsFavorited);

        favoriteButton.innerHTML = `
            <i data-lucide="heart"></i>
            ${newIsFavorited ? "已收藏" : "收藏老師"}
        `;

        lucide.createIcons();

    } catch (error) {
        console.error("收藏老師操作失敗：", error);
        alert(error.message);

    } finally {
        favoriteButton.disabled = false;
    }
}

// ==============================
// 顯示教學科目與年級
// ==============================
function renderTeacherTags(teacher) {

    const subjects = (teacher.subjects || []).map(function (subject) {
        return subjectNameMap[subject] ?? subject;
    });

    const grades = (teacher.grades || []).map(function (grade) {
        return gradeNameMap[grade] ?? grade;
    });

    const headerTags = document.getElementById("detail-header-tags");
    const subjectContainer = document.getElementById("detail-subjects");
    const gradeContainer = document.getElementById("detail-grades");

    headerTags.replaceChildren();
    subjectContainer.replaceChildren();
    gradeContainer.replaceChildren();

    // 教學科目
    subjects.forEach(function (subject) {

        const headerTag = document.createElement("span");
        headerTag.className = "detail-subject-tag";
        headerTag.textContent = subject;
        headerTags.appendChild(headerTag);

        const subjectTag = document.createElement("span");
        subjectTag.className = "detail-subject-tag";
        subjectTag.textContent = subject;
        subjectContainer.appendChild(subjectTag);
    });

    // 教學年級
    grades.forEach(function (grade) {

        const gradeTag = document.createElement("span");
        gradeTag.className = "detail-grade-tag";
        gradeTag.textContent = grade;
        gradeContainer.appendChild(gradeTag);
    });

    // 基本資料上方的年級標籤合併顯示
    if (grades.length > 0) {
        const headerGrade = document.createElement("span");
        headerGrade.className = "detail-grade-tag";
        headerGrade.textContent = grades.join("、");

        headerTags.appendChild(headerGrade);
    }
}

// ==============================
// 顯示授課地區
// ==============================
function renderTeacherLocations(locations) {

    const container = document.getElementById("detail-locations");

    container.replaceChildren();

    if (locations.length === 0) {
        container.textContent = "尚未設定授課地區";
        return;
    }

    locations.forEach(function (location) {

        const tag = document.createElement("span");

        tag.textContent = `${location.city}・${location.district}`;

        container.appendChild(tag);
    });
}

// ==============================
// 顯示可授課時段
// ==============================
function renderTeacherSchedule(availability) {

    const tbody = document.getElementById("detail-schedule-body");

    tbody.replaceChildren();

    // 星期順序：週日 → 週六
    // MySQL：1 = 週一，7 = 週日
    const days = [7, 1, 2, 3, 4, 5, 6];

    // 時段：上午、下午、晚上
    const periods = [
        { key: "morning", label: "上午" },
        { key: "afternoon", label: "下午" },
        { key: "evening", label: "晚上" }
    ];

    // 儲存可授課的星期與時段
    // 將資料庫的星期與時段整理成 Set
    // Number() 確保星期以數字進行比對
    const availableSet = new Set(
        availability.map(function (item) {
            return `${Number(item.day)}-${item.period}`;
        })
    );

    // 建立三列時段
    periods.forEach(function (period) {

        const row = document.createElement("tr");

        const header = document.createElement("th");
        header.textContent = period.label;

        row.appendChild(header);

        // 每列建立七個星期欄位
        days.forEach(function (day) {

            const cell = document.createElement("td");

            // 公開老師頁：可點擊授課時段
            if (availableSet.has(`${day}-${period.key}`)) {
                cell.className = "available";

                cell.innerHTML = `
                    <span class="schedule-desktop-text">✓ 可授課</span>
                    <span class="schedule-mobile-text">✓</span>
                `;

            } else {
                cell.textContent = "—";
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });
}

// ==============================
// 老師資料載入失敗
// ==============================
function showTeacherError(message) {

    // 隱藏原本的測試資料，避免誤認成真正的老師資訊
    const detailCards = document.querySelectorAll(".teacher-detail-page .detail-card");

    detailCards.forEach(function (card) {
        card.hidden = true;
    });

    // 在頁面中顯示錯誤訊息
    const main = document.querySelector(".teacher-detail-page");

    const errorMessage = document.createElement("p");
    errorMessage.className = "detail-error-message";
    errorMessage.textContent = message;

    main.appendChild(errorMessage);
}

// ==============================
// 初始化老師詳細介紹頁面
// ==============================

// 取得所有老師資料卡片
const detailCards = document.querySelectorAll(
    ".teacher-detail-page .detail-card"
);

// 資料載入前先隱藏，避免顯示不完整內容
detailCards.forEach(function (card) {
    card.hidden = true;
});

// 開始載入指定老師資料
loadTeacherDetail();

// ==============================
// 會員登入、登出時立即更新老師頁面
// ==============================

// 登入成功後重新確認老師身分
window.addEventListener(
    "tutorlink:login",
    refreshTeacherDetailActions
);

// 登出成功後重新確認老師身分
window.addEventListener(
    "tutorlink:logout",
    refreshTeacherDetailActions
);

 // ==============================
 // 刪除老師資料確認視窗
 // ==============================
const deleteButton = document.getElementById("detail-delete-button");
const deleteModal = document.getElementById("detail-delete-modal");
const deleteCancelButton = document.getElementById("detail-delete-cancel");
const deleteConfirmButton = document.getElementById("detail-delete-confirm");
const deleteError = document.getElementById("detail-delete-error");

let deleteModalPreviousFocus = null;

// 開啟確認視窗
function openDeleteModal() {
    deleteModalPreviousFocus = document.activeElement;
    deleteError.hidden = true;
    deleteError.textContent = "";

    deleteModal.hidden = false;
    deleteCancelButton.focus();
}

// 關閉確認視窗
function closeDeleteModal() {
    // 刪除請求進行中，不允許關閉
    if (deleteConfirmButton.disabled) {
        return;
    }

    deleteModal.hidden = true;

    if (deleteModalPreviousFocus?.isConnected) {
        deleteModalPreviousFocus.focus();
    }
}

// 點擊刪除老師資料
deleteButton.addEventListener("click", openDeleteModal);

// 點擊取消
deleteCancelButton.addEventListener("click", closeDeleteModal);

// 點擊背景遮罩
deleteModal.addEventListener("click", function (event) {
    if (event.target === deleteModal) {
        closeDeleteModal();
    }
});

// 按下 Esc 關閉視窗
document.addEventListener("keydown", function (event) {
    if (deleteModal.hidden) {
        return;
    }

    if (event.key === "Escape") {
        event.preventDefault();
        closeDeleteModal();
    }

    // 將 Tab 鍵盤焦點限制在確認視窗內
    if (event.key === "Tab") {
        const focusableButtons = [
            deleteCancelButton,
            deleteConfirmButton
        ].filter(button => !button.disabled);

        if (focusableButtons.length === 0) {
            event.preventDefault();
            return;
        }

        const firstButton = focusableButtons[0];
        const lastButton = focusableButtons[focusableButtons.length - 1];

        if (event.shiftKey && document.activeElement === firstButton) {
            event.preventDefault();
            lastButton.focus();
        } else if (!event.shiftKey && document.activeElement === lastButton) {
            event.preventDefault();
            firstButton.focus();
        }
    }
});

 // ==============================
 // 確認刪除老師資料
 // ==============================
deleteConfirmButton.addEventListener("click", async function () {

    // 避免重複送出刪除請求
    if (deleteConfirmButton.disabled) {
        return;
    }

    // 取得登入憑證
    const token = sessionStorage.getItem("tutorlink_token");

    if (!token) {
        deleteError.textContent = "登入狀態已失效，請重新登入。";
        deleteError.hidden = false;
        return;
    }

    // 刪除期間停用操作按鈕
    deleteConfirmButton.disabled = true;
    deleteCancelButton.disabled = true;
    deleteConfirmButton.textContent = "刪除中...";

    deleteError.hidden = true;
    deleteError.textContent = "";

    try {
        // 呼叫刪除老師資料 API
        const response = await fetch("/api/teachers/me", {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error("登入狀態已失效，請重新登入。");
            }

            if (response.status === 404) {
                throw new Error("找不到您的老師資料，可能已經被刪除。");
            }

            throw new Error("刪除老師資料失敗，請稍後再試。");
        }

        // 刪除成功後回到首頁
        window.location.replace("/");

    } catch (error) {
        console.error("刪除老師資料失敗：", error);

        deleteError.textContent = error.message;
        deleteError.hidden = false;

    } finally {
        deleteConfirmButton.disabled = false;
        deleteCancelButton.disabled = false;
        deleteConfirmButton.textContent = "確認刪除";
    }
});

// ==============================
// 返回老師詳細頁時更新收藏狀態
// ==============================
window.addEventListener("pageshow", function (event) {

    // 只有從瀏覽器上一頁快取恢復時才重新查詢
    if (!event.persisted) {
        return;
    }

    // 只處理公開老師詳細頁
    if (isMyTeacherProfilePage) {
        return;
    }

    // 確認老師 ID 有效
    if (!teacherId || !/^[1-9]\d*$/.test(teacherId)) {
        return;
    }

    // 重新確認目前會員的收藏狀態
    loadFavoriteStatus(teacherId);
});

// ==============================
// 預約家教課程 Modal
// ==============================

// 記錄學生選擇的星期與時段
let selectedBookingWeekday = null;
let selectedBookingPeriod = null;

// 取得預約視窗元素
const bookingModal = document.getElementById("booking-modal");
const bookingModalClose = document.getElementById("booking-modal-close");
const bookingFormCancel = document.getElementById("booking-form-cancel");

const bookingDateTrigger = document.getElementById("booking-date-trigger");
const bookingDateDisplay = document.getElementById("booking-date-display");
const bookingCalendar = document.getElementById("booking-calendar");

// 展開或收合月曆
function toggleBookingCalendar(forceOpen) {
    if (!bookingCalendar || !bookingDateTrigger) return;

    const shouldOpen =
        typeof forceOpen === "boolean"
            ? forceOpen
            : bookingCalendar.hidden;

    bookingCalendar.hidden = !shouldOpen;

    bookingDateTrigger.setAttribute(
        "aria-expanded",
        String(shouldOpen)
    );
}

// 將 YYYY-MM-DD 轉換成中文日期
function formatBookingDate(dateString) {
    const [year, month, day] = dateString.split("-").map(Number);

    const date = new Date(Date.UTC(year, month - 1, day));
    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];

    return `${year}年${month}月${day}日（${weekdays[date.getUTCDay()]}）`;
}

// 更新日期欄位顯示
function updateBookingDateDisplay(dateString) {
    if (!bookingDateDisplay || !bookingDateTrigger) return;

    bookingDateDisplay.textContent = dateString
        ? formatBookingDate(dateString)
        : "請選擇上課日期";

    bookingDateTrigger.classList.toggle(
        "has-value",
        Boolean(dateString)
    );
}

// 點擊日期欄位時切換月曆
bookingDateTrigger?.addEventListener("click", () => {
    toggleBookingCalendar();
});

// 開啟預約視窗
function openBookingModal(weekday, period) {
    if (!bookingModal) return;

    // 記錄選擇的星期與時段
    selectedBookingWeekday = weekday;
    selectedBookingPeriod = period;

    // 清除上一次選擇的日期
    const bookingDate = document.getElementById("booking-date");
    if (bookingDate) {
        bookingDate.value = "";
    }

    // 顯示預約視窗
    bookingModal.hidden = false;

    // 初始化預約月曆
    initializeBookingCalendar();

    // 清空日期欄位文字
    updateBookingDateDisplay("");

    // 預設收合月曆
    toggleBookingCalendar(false);

    // 顯示目前課程長度的預估金額
    updateBookingEstimatedPrice();

    // 將焦點移到關閉按鈕
    bookingModalClose?.focus();
}

// 關閉預約視窗
function closeBookingModal() {
    if (!bookingModal) return;

    bookingModal.hidden = true;
}

// 點擊右上角 X
bookingModalClose?.addEventListener("click", closeBookingModal);

// 點擊取消按鈕
bookingFormCancel?.addEventListener("click", closeBookingModal);

// 點擊背景遮罩
bookingModal
    ?.querySelector(".booking-modal-overlay")
    ?.addEventListener("click", closeBookingModal);

// 按下 Escape 關閉視窗
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && bookingModal && !bookingModal.hidden) {
        closeBookingModal();
    }
});

// ==============================
// 預約視窗：載入老師授課科目
// ==============================
function renderBookingSubjects(subjects) {
    const subjectSelect = document.getElementById("booking-subject");

    if (!subjectSelect) return;

    // 清空原本的選項
    subjectSelect.replaceChildren();

    // 預設提示選項
    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "請選擇授課科目";
    defaultOption.disabled = true;
    defaultOption.selected = true;

    subjectSelect.appendChild(defaultOption);

    // 加入老師實際教授的科目
    subjects.forEach((subject) => {
        const option = document.createElement("option");

        // 保留英文代碼，方便之後傳送 API
        option.value = subject;

        // 顯示中文科目名稱
        option.textContent = subjectNameMap[subject] ?? subject;

        subjectSelect.appendChild(option);
    });
}

// ==============================
// 預約視窗：自訂月曆
// ==============================

// 目前顯示的月份
let bookingCalendarYear = null;
let bookingCalendarMonth = null;

// 取得台灣今天的年月日
function getTaiwanToday() {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "Asia/Taipei",
        year: "numeric",
        month: "2-digit",
        day: "2-digit"
    }).formatToParts(new Date());

    const values = Object.fromEntries(
        parts.map((part) => [part.type, part.value])
    );

    return {
        year: Number(values.year),
        month: Number(values.month) - 1,
        day: Number(values.day)
    };
}

// 初始化月曆
function initializeBookingCalendar() {
    const today = getTaiwanToday();

    bookingCalendarYear = today.year;
    bookingCalendarMonth = today.month;

    const bookingDate = document.getElementById("booking-date");

    if (bookingDate) {
        bookingDate.value = "";
    }

    renderBookingCalendar();

    // 尚未選擇日期，先停用開始時間
    resetBookingStartTime();
}

// 繪製月曆
function renderBookingCalendar() {
    const calendar = document.getElementById("booking-calendar");

    if (!calendar || currentTeacherAvailability.length === 0) return;

    calendar.replaceChildren();

    const today = getTaiwanToday();

    const firstDay = new Date(Date.UTC(
        bookingCalendarYear,
        bookingCalendarMonth,
        1
    ));

    const daysInMonth = new Date(Date.UTC(
        bookingCalendarYear,
        bookingCalendarMonth + 1,
        0
    )).getUTCDate();

    // 月曆標題
    const header = document.createElement("div");
    header.className = "booking-calendar-header";

    const prevButton = document.createElement("button");
    prevButton.type = "button";
    prevButton.className = "booking-calendar-nav";
    prevButton.textContent = "‹";
    prevButton.setAttribute("aria-label", "上個月");

    const monthTitle = document.createElement("strong");
    monthTitle.textContent =
        `${bookingCalendarYear} 年 ${bookingCalendarMonth + 1} 月`;

    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.className = "booking-calendar-nav";
    nextButton.textContent = "›";
    nextButton.setAttribute("aria-label", "下個月");

    // 不允許切換到過去月份
    prevButton.disabled =
        bookingCalendarYear === today.year &&
        bookingCalendarMonth === today.month;

    prevButton.addEventListener("click", () => {
        changeBookingCalendarMonth(-1);
    });

    nextButton.addEventListener("click", () => {
        changeBookingCalendarMonth(1);
    });

    header.append(prevButton, monthTitle, nextButton);
    calendar.appendChild(header);

    // 日期格子
    const grid = document.createElement("div");
    grid.className = "booking-calendar-grid";

    // 星期標題
    ["日", "一", "二", "三", "四", "五", "六"].forEach((day) => {
        const weekday = document.createElement("div");
        weekday.className = "booking-calendar-weekday";
        weekday.textContent = day;

        grid.appendChild(weekday);
    });

    // 月初空白格
    for (let i = 0; i < firstDay.getUTCDay(); i++) {
        const empty = document.createElement("div");
        grid.appendChild(empty);
    }

    // 建立日期
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(Date.UTC(
            bookingCalendarYear,
            bookingCalendarMonth,
            day
        ));

        // JavaScript：週日 = 0
        // 資料庫：週日 = 7
        const jsWeekday = date.getUTCDay();
        const dbWeekday = jsWeekday === 0 ? 7 : jsWeekday;

        const dateString =
            `${bookingCalendarYear}-` +
            `${String(bookingCalendarMonth + 1).padStart(2, "0")}-` +
            `${String(day).padStart(2, "0")}`;

        const todayString =
            `${today.year}-` +
            `${String(today.month + 1).padStart(2, "0")}-` +
            `${String(today.day).padStart(2, "0")}`;

        // 取得老師所有開放授課的星期
        const availableWeekdays = new Set(
            currentTeacherAvailability.map((item) => Number(item.day))
        );

        // 符合老師開放的星期，而且不能是過去日期
        const isAvailable =
            availableWeekdays.has(dbWeekday) &&
            dateString >= todayString;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "booking-calendar-day";
        button.textContent = day;
        button.disabled = !isAvailable;

        if (isAvailable) {
            button.classList.add("available");

            button.addEventListener("click", () => {
                selectBookingDate(dateString);
            });
        }

        const selectedDate =
            document.getElementById("booking-date")?.value;

        if (selectedDate === dateString) {
            button.classList.add("selected");
            button.setAttribute("aria-pressed", "true");
        }

        grid.appendChild(button);
    }

    calendar.appendChild(grid);
}

// 切換月份
function changeBookingCalendarMonth(offset) {
    const newMonth = new Date(Date.UTC(
        bookingCalendarYear,
        bookingCalendarMonth + offset,
        1
    ));

    bookingCalendarYear = newMonth.getUTCFullYear();
    bookingCalendarMonth = newMonth.getUTCMonth();

    // 切換月份時清除已選日期
    const bookingDate = document.getElementById("booking-date");

    if (bookingDate) {
        bookingDate.value = "";
        updateBookingDateDisplay("");
    }

    renderBookingCalendar();

    // 切換月份後，清空開始時間
    resetBookingStartTime();
}

// 選擇日期
function selectBookingDate(dateString) {
    const bookingDate = document.getElementById("booking-date");

    if (!bookingDate) return;

    // 記錄選擇的日期
    bookingDate.value = dateString;

    // 更新月曆選取狀態
    renderBookingCalendar();

    // 更新日期欄位文字
    updateBookingDateDisplay(dateString);

    // 選取後自動收合月曆
    toggleBookingCalendar(false);

    // 更新該日期可選擇的開始時間
    renderBookingStartTimes(dateString);
}

// ==============================
// 預約上課按鈕
// ==============================
const detailBookingButton = document.getElementById(
    "detail-booking-button"
);

detailBookingButton?.addEventListener("click", () => {

    // 未登入：先顯示登入視窗
    const token = sessionStorage.getItem("tutorlink_token");

    if (!token) {
        openAuthModal("login");
        return;
    }

    // 老師沒有開放時段
    if (currentTeacherAvailability.length === 0) {
        return;
    }

    // 開啟預約視窗，不預先限制星期與時段
    openBookingModal(null, null);
});

// ==============================
// 預約視窗：開始時間選單
// ==============================

// 老師授課時段對應的實際時間
const bookingPeriodTimes = {
    morning: { start: "08:00", end: "12:00" },
    afternoon: { start: "12:00", end: "18:00" },
    evening: { start: "18:00", end: "22:00" }
};

// HH:MM 轉換成分鐘
function bookingTimeToMinutes(time) {
    const [hours, minutes] = time.split(":").map(Number);
    return hours * 60 + minutes;
}

// 分鐘轉換成 HH:MM
function bookingMinutesToTime(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    return (
        String(hours).padStart(2, "0") +
        ":" +
        String(minutes).padStart(2, "0")
    );
}

// 清空開始時間選單
function resetBookingStartTime() {
    const select = document.getElementById("booking-start-time");

    if (!select) return;

    select.replaceChildren();

    const option = document.createElement("option");
    option.value = "";
    option.textContent = "請先選擇上課日期";

    select.appendChild(option);
    select.disabled = true;
}

// 依照選擇日期及課程長度產生上課時間
function renderBookingStartTimes(dateString) {
    const select = document.getElementById("booking-start-time");

    if (!select) return;

    // 保留原本選擇的開始時間
    const previousTime = select.value;

    select.replaceChildren();
    select.disabled = true;

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "請選擇上課時間";
    select.appendChild(defaultOption);

    if (!dateString) {
        resetBookingStartTime();
        return;
    }

    // 取得目前選擇的課程長度
    const duration = Number(
        document.querySelector(
            'input[name="booking-duration"]:checked'
        )?.value || 90
    );

    // 取得日期對應的星期
    const [year, month, day] = dateString.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));

    const jsWeekday = date.getUTCDay();
    const dbWeekday = jsWeekday === 0 ? 7 : jsWeekday;

    // 找出老師當天開放的所有時段
    const availableRanges = currentTeacherAvailability
        .filter((item) => Number(item.day) === dbWeekday)
        .map((item) => bookingPeriodTimes[item.period])
        .filter(Boolean)
        .map((period) => ({
            start: bookingTimeToMinutes(period.start),
            end: bookingTimeToMinutes(period.end)
        }))
        .sort((a, b) => a.start - b.start);

    // 合併連續或重疊的時段
    const mergedRanges = [];

    availableRanges.forEach((range) => {
        const lastRange = mergedRanges[mergedRanges.length - 1];

        if (lastRange && range.start <= lastRange.end) {
            lastRange.end = Math.max(lastRange.end, range.end);
        } else {
            mergedRanges.push({ ...range });
        }
    });

    // 取得台灣目前日期與時間
    const nowParts = new Intl.DateTimeFormat("en-GB", {
        timeZone: "Asia/Taipei",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23"
    }).formatToParts(new Date());

    const now = Object.fromEntries(
        nowParts.map((part) => [part.type, part.value])
    );

    const todayString =
        `${now.year}-${now.month}-${now.day}`;

    const currentMinutes =
        Number(now.hour) * 60 + Number(now.minute);

    const availableTimes = [];

    // 每 30 分鐘產生一個上課時間選項
    mergedRanges.forEach((range) => {
        for (
            let start = range.start;
            start + duration <= range.end;
            start += 30
        ) {
            // 今天不能選擇已經過去的時間
            if (
                dateString === todayString &&
                start <= currentMinutes
            ) {
                continue;
            }

            availableTimes.push(start);
        }
    });

    // 日期已過去時，不提供上課時間
    if (dateString < todayString) {
        availableTimes.length = 0;
    }

    // 產生完整上課時段，例如 19:00 – 20:30
    availableTimes.forEach((minutes) => {
        const option = document.createElement("option");

        const startTime = bookingMinutesToTime(minutes);
        const endTime = bookingMinutesToTime(minutes + duration);

        // 後端 API 仍只需要開始時間
        option.value = startTime;

        // 前端顯示完整上課時段
        option.textContent = `${startTime} – ${endTime}`;

        select.appendChild(option);
    });

    select.disabled = availableTimes.length === 0;

    if (availableTimes.length === 0) {
        defaultOption.textContent = "當天沒有符合課程長度的時間";
        return;
    }

    // 原本選擇的開始時間仍有效，才保留
    if (
        availableTimes.some(
            (minutes) =>
                bookingMinutesToTime(minutes) === previousTime
        )
    ) {
        select.value = previousTime;
    }
}

// ==============================
// 預約視窗：預估課程金額
// ==============================
function updateBookingEstimatedPrice() {
    // 取得目前選擇的課程長度
    const duration = Number(
        document.querySelector(
            'input[name="booking-duration"]:checked'
        )?.value || 90
    );

    // 計算預估課程金額
    const estimatedPrice =
        Number(currentTeacherHourlyRate) * (duration / 60);

    // 取得金額顯示元素
    const priceElement = document.getElementById("booking-total-amount");

    if (!priceElement) return;

    // 顯示金額
    priceElement.textContent =
        `NT$ ${Math.round(estimatedPrice).toLocaleString("en-US")}`;
}

// ==============================
// 預約視窗：課程長度變更
// ==============================
document.querySelectorAll(
    'input[name="booking-duration"]'
).forEach((radio) => {

    radio.addEventListener("change", () => {
        // 更新預估金額
        updateBookingEstimatedPrice();

        const bookingDate = document.getElementById("booking-date");

        if (!bookingDate?.value) {
            resetBookingStartTime();
            return;
        }

        // 依新的課程長度重新篩選開始時間
        renderBookingStartTimes(bookingDate.value);
    });

});

// ==============================
// 預約視窗：必填欄位驗證
// ==============================
const bookingForm = document.getElementById("booking-form");
const bookingFormError = document.getElementById("booking-form-error");

// 顯示表單錯誤訊息
function showBookingFormError(message) {
    if (!bookingFormError) return;

    bookingFormError.textContent = message;
    bookingFormError.hidden = false;
}

// 清除表單錯誤訊息
function clearBookingFormError() {
    if (!bookingFormError) return;

    bookingFormError.textContent = "";
    bookingFormError.hidden = true;
}

// 驗證預約表單
function validateBookingForm() {
    const subject = document.getElementById("booking-subject");
    const date = document.getElementById("booking-date");
    const startTime = document.getElementById("booking-start-time");

    const duration = document.querySelector(
        'input[name="booking-duration"]:checked'
    );

    clearBookingFormError();

    // 1. 授課科目
    if (!subject?.value) {
        showBookingFormError("請選擇授課科目");
        subject?.focus();
        return false;
    }

    // 2. 上課日期
    if (!date?.value) {
        showBookingFormError("請選擇上課日期");
        bookingDateTrigger?.focus();
        return false;
    }

    // 3. 課程長度
    if (!duration || !["60", "90", "120"].includes(duration.value)) {
        showBookingFormError("請選擇有效的課程長度");
        document.querySelector(
            'input[name="booking-duration"]'
        )?.focus();
        return false;
    }

    // 4. 開始時間
    if (!startTime?.value) {
        showBookingFormError("請選擇上課時間");
        startTime?.focus();
        return false;
    }

    // 5. 確認開始時間仍是有效選項
    const validTime = [...startTime.options].some(
        (option) =>
            option.value === startTime.value &&
            !option.disabled
    );

    if (startTime.disabled || !validTime) {
        showBookingFormError("開始時間無效，請重新選擇");
        startTime.focus();
        return false;
    }

    return true;
}

// ==============================
// 預約視窗：送出預約申請
// ==============================
bookingForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    // 先檢查必填欄位
    if (!validateBookingForm()) {
        return;
    }

    const token = sessionStorage.getItem("tutorlink_token");
    const submitButton = document.getElementById("booking-form-submit");

    // 確認登入狀態
    if (!token) {
        showBookingFormError("登入狀態已失效，請重新登入");
        return;
    }

    // 確認老師 ID
    if (!teacherId || !/^[1-9]\d*$/.test(teacherId)) {
        showBookingFormError("老師資料有誤，請重新整理頁面");
        return;
    }

    // 防止重複送出
    if (submitButton?.disabled) {
        return;
    }

    const subject = document.getElementById("booking-subject").value;
    const bookingDate = document.getElementById("booking-date").value;
    const startTime = document.getElementById("booking-start-time").value;

    const duration = Number(
        document.querySelector(
            'input[name="booking-duration"]:checked'
        ).value
    );

    // 對應後端 BookingCreate 模型
    const bookingData = {
        teacher_id: Number(teacherId),
        subject: subject,
        booking_date: bookingDate,
        start_time: startTime,
        duration_minutes: duration
    };

    const originalButtonText = submitButton?.textContent;

    try {
        clearBookingFormError();

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "送出中...";
        }

        const response = await fetch("/api/bookings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(bookingData)
        });

        const result = await response.json();

        // 後端驗證失敗
        if (!response.ok) {
            let errorMessage = "預約申請失敗，請稍後再試";

            if (typeof result.detail === "string") {
                errorMessage = result.detail;
            }

            if (response.status === 401) {
                errorMessage = "登入狀態已失效，請重新登入";
            }

            showBookingFormError(errorMessage);
            return;
        }

        // 確認後端回傳聊天室 ID
        if (!result.conversation_id) {
            showBookingFormError(
                "預約已建立，但無法取得聊天室資訊，請前往我的訊息查看"
            );
            return;
        }

        // 預約成功後導向對應聊天室
        window.location.href =
            `/messages.html?conversation_id=${encodeURIComponent(result.conversation_id)}`;

    } catch (error) {
        console.error("送出預約申請失敗：", error);

        showBookingFormError(
            "網路連線異常，請先至我的訊息確認預約是否已建立，避免重複送出"
        );

    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
        }
    }
});

// ==============================
// 查詢目前會員對指定老師的評價資格
// ==============================
async function getMyTeacherReviewStatus(teacherId) {
    const token = sessionStorage.getItem("tutorlink_token");

    // 統一未具備評價資格時的回傳資料
    const emptyStatus = {
        eligible: false,
        hasReview: false,
        reviewId: null,
        reviewContent: "",
        bookingId: null
    };

    // 未登入不能撰寫或編輯評價
    if (!token) {
        return emptyStatus;
    }

    const response = await fetch("/api/bookings/me", {
        headers: {
            "Authorization": `Bearer ${token}`
        },
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error("無法確認評價資格");
    }

    const data = await response.json();

    // 會員已切換時，不使用舊會員的預約資料
    if (sessionStorage.getItem("tutorlink_token") !== token) {
        return null;
    }

    const bookings = Array.isArray(data.bookings)
        ? data.bookings
        : [];

    // 僅接受目前會員以學生身分完成的課程
    const completedBookings = bookings.filter((booking) => {
        return (
            Number(booking.teacher_id) === Number(teacherId) &&
            booking.is_student_booking === true &&
            booking.completed_at != null
        );
    });

    // 沒有完成課程就沒有評價資格
    if (completedBookings.length === 0) {
        return emptyStatus;
    }

    // 查詢該學生對這位老師是否已有評價
    const reviewedBooking = completedBookings.find((booking) => {
        return booking.review_id != null;
    });

    return {
        eligible: true,
        hasReview: Boolean(reviewedBooking),
        reviewId: reviewedBooking?.review_id ?? null,
        reviewContent: reviewedBooking?.review_content ?? "",
        bookingId: completedBookings[0].id
    };
}

 // ==============================
 // 載入老師公開課後評價
 // ==============================
async function loadTeacherReviews(teacherId) {
    const section = document.getElementById("detail-reviews-section");
    const count = document.getElementById("detail-reviews-count");
    const list = document.getElementById("detail-reviews-list");

    // 只在有評價區的頁面執行
    if (!section || !count || !list) return;

    count.textContent = "載入評價中...";
    list.replaceChildren();

    try {
        const response = await fetch(
            `/api/teachers/${encodeURIComponent(teacherId)}/reviews`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error("評價資料載入失敗");
        }

        const data = await response.json();
        const reviews = Array.isArray(data.reviews)
            ? data.reviews
            : [];

        // 取得目前登入會員的評價資格
        const token = sessionStorage.getItem("tutorlink_token");

        let myReviewId = null;
        let isReviewTeacherOwner = false;

        if (token) {
            try {
                const ownerResponse = await fetch("/api/teachers/me", {
                    headers: {
                        "Authorization": `Bearer ${token}`
                    },
                    cache: "no-store"
                });

                if (ownerResponse.ok) {
                    const ownerData = await ownerResponse.json();

                    isReviewTeacherOwner =
                        Number(ownerData.teacher?.id) === Number(teacherId);
                }

                if (sessionStorage.getItem("tutorlink_token") !== token) {
                    return;
                }
            } catch (error) {
                console.error("確認評價老師身分失敗：", error);
            }
        }

        if (token) {
            try {
                const status = await getMyTeacherReviewStatus(teacherId);

                // 查詢期間如果會員切換，捨棄舊結果
                if (sessionStorage.getItem("tutorlink_token") !== token) {
                    return;
                }

                if (status?.hasReview) {
                    myReviewId = Number(status.reviewId);
                }
            } catch (error) {
                console.error("查詢我的評價狀態失敗：", error);
            }
        }

        // 將自己的評價排在最上方
        const sortedReviews = [...reviews].sort((a, b) => {
            const aIsMine = Number(a.id) === myReviewId;
            const bIsMine = Number(b.id) === myReviewId;

            return Number(bIsMine) - Number(aIsMine);
        });

        count.textContent = `共 ${reviews.length} 則評價`;

        // 已完成課程、尚未評價：顯示撰寫評價入口
        if (token && !isReviewTeacherOwner && myReviewId === null) {
            try {
                const status = await getMyTeacherReviewStatus(teacherId);

                // 避免登入會員已切換時顯示舊資料
                if (sessionStorage.getItem("tutorlink_token") !== token) {
                    return;
                }

                if (status?.eligible && !status.hasReview) {
                    const actionArea = document.createElement("div");
                    actionArea.className = "detail-review-write-area";

                    const message = document.createElement("p");
                    message.textContent =
                        "你已完成這位老師的課程，歡迎分享上課心得。";

                    const writeButton = document.createElement("button");
                    writeButton.type = "button";
                    writeButton.className = "detail-review-edit-button";
                    writeButton.id = "detail-review-write-button";

                    const icon = document.createElement("i");
                    icon.setAttribute("data-lucide", "pencil-line");

                    const text = document.createElement("span");
                    text.textContent = "撰寫評價";

                    writeButton.append(icon, text);

                    writeButton.addEventListener("click", function () {
                        openDetailReviewModal("create");
                    });

                    actionArea.append(message, writeButton);

                    list.appendChild(actionArea);

                    if (window.lucide) {
                        lucide.createIcons();
                    }
                }
            } catch (error) {
                console.error("確認撰寫評價資格失敗：", error);
            }
        }

        if (reviews.length === 0) {
            const empty = document.createElement("p");
            empty.className = "detail-reviews-empty";
            empty.textContent = "目前尚無學生評價";
            list.appendChild(empty);
            return;
        }

        sortedReviews.forEach(function (review) {
            // 每組學生評價與老師回覆的外層容器
            const reviewGroup = document.createElement("div");
            reviewGroup.className = "detail-review-group";

            const item = document.createElement("article");
            item.className = "detail-review-item";
            item.dataset.reviewId = review.id;

            // ==============================
            // 學生名稱與日期
            // ==============================
            const header = document.createElement("div");
            header.className = "detail-review-header";

            const name = document.createElement("strong");
            name.className = "detail-review-name";
            name.textContent = review.student_name || "學生會員";

            const date = document.createElement("time");
            date.className = "detail-review-date";

            if (review.created_at) {
                date.dateTime = review.created_at;
                date.textContent = review.created_at
                    .slice(0, 10)
                    .replaceAll("-", "/");
            }

            header.append(name, date);

            // ==============================
            // 學生評價內容
            // ==============================
            const content = document.createElement("p");
            content.className = "detail-review-content detail-review-content-display";

            const contentText = document.createElement("span");
            contentText.textContent = review.content || "";

            content.appendChild(contentText);

            // 學生有編輯過才顯示（已編輯）
            if (review.review_edited_at) {
                const edited = document.createElement("span");
                edited.className = "detail-review-edited";
                edited.textContent = "（已編輯）";
                edited.style.color = "#999";
                edited.style.fontSize = "12px";
                edited.style.marginLeft = "6px";

                content.appendChild(edited);
            }

            item.append(header, content);

            // ==============================
            // 學生自己的評價：顯示編輯按鈕
            // ==============================
            if (
                !isReviewTeacherOwner &&
                myReviewId !== null &&
                Number(review.id) === myReviewId
            ) {
                // 標示這是目前學生自己的評價
                item.classList.add("detail-review-mine");

                const actionArea = document.createElement("div");
                actionArea.className = "detail-review-actions";

                const editButton = document.createElement("button");
                editButton.type = "button";
                editButton.className = "detail-review-edit-button";

                const editIcon = document.createElement("i");
                editIcon.setAttribute("data-lucide", "pencil");

                const editText = document.createElement("span");
                editText.textContent = "編輯評價";

                editButton.append(editIcon, editText);

                editButton.addEventListener("click", function () {
                    openDetailReviewModal(
                        "edit",
                        review.id,
                        review.content || ""
                    );
                });

                actionArea.appendChild(editButton);
                item.appendChild(actionArea);
            }

            // 先加入學生評價，讓老師回覆顯示在下方
            reviewGroup.appendChild(item);

            // ==============================
            // 老師回覆
            // ==============================
            if (review.teacher_reply) {
                const reply = document.createElement("div");
                reply.className = "detail-review-reply";

                const replyTitle = document.createElement("strong");
                replyTitle.className = "detail-review-reply-title";
                replyTitle.textContent = "老師回覆";

                const replyContent = document.createElement("p");
                replyContent.className = "detail-review-reply-content";

                const replyText = document.createElement("span");
                replyText.textContent = review.teacher_reply;

                replyContent.appendChild(replyText);

                // 老師有編輯過才顯示（已編輯）
                if (review.teacher_reply_edited_at) {
                    const edited = document.createElement("span");
                    edited.className = "detail-review-edited";
                    edited.textContent = "（已編輯）";
                    edited.style.color = "#999";
                    edited.style.fontSize = "12px";
                    edited.style.marginLeft = "6px";

                    replyContent.appendChild(edited);
                }

                reply.append(replyTitle, replyContent);
                reviewGroup.appendChild(reply);
            }

            // 老師本人：顯示回覆或編輯回覆按鈕
            if (isReviewTeacherOwner) {
                const replyActions = document.createElement("div");
                replyActions.className = "detail-review-actions";

                const replyButton = document.createElement("button");
                replyButton.type = "button";
                replyButton.className = "detail-review-edit-button";

                const hasReply = Boolean(review.teacher_reply);
                replyButton.dataset.reviewId = review.id;
                replyButton.dataset.replyContent = review.teacher_reply || "";

                const replyIcon = document.createElement("i");
                replyIcon.setAttribute(
                    "data-lucide",
                    hasReply ? "pencil" : "message-square-plus"
                );

                const replyText = document.createElement("span");
                replyText.textContent = hasReply ? "編輯回覆" : "回覆評價";

                replyButton.append(replyIcon, replyText);

                replyButton.addEventListener("click", function () {
                    openDetailReviewModal(
                        hasReply ? "reply-edit" : "reply",
                        review.id,
                        review.teacher_reply || ""
                    );
                });

                replyActions.appendChild(replyButton);

                if (hasReply) {
                    // 已有回覆：將編輯按鈕放進老師回覆框
                    const teacherReply = reviewGroup.querySelector(
                        ".detail-review-reply"
                    );

                    if (teacherReply) {
                        teacherReply.appendChild(replyActions);
                    }
                } else {
                    // 尚未回覆：按鈕放在學生評價框外面
                    reviewGroup.appendChild(replyActions);
                }
            }

            list.appendChild(reviewGroup);
        });

        // 更新評價區新增的 Lucide 圖示
        if (window.lucide) {lucide.createIcons();}

        // 從通知中心進入：定位指定評論
        const params = new URLSearchParams(window.location.search);
        const targetReviewId = params.get("review_id");

        if (
            targetReviewId &&
            window.location.hash === "#detail-reviews-section"
        ) {
            const targetReview = Array.from(
                list.querySelectorAll(".detail-review-item")
            ).find(
                (item) => item.dataset.reviewId === targetReviewId
            );

            if (targetReview) {
                requestAnimationFrame(() => {
                    targetReview.scrollIntoView({
                        behavior: "smooth",
                        block: "center"
                    });
                });
            }
        }

    } catch (error) {
        console.error("載入學生評價失敗：", error);
        count.textContent = "";
        list.replaceChildren();

        const message = document.createElement("p");
        message.className = "detail-reviews-error";
        message.textContent = "目前無法載入學生評價，請稍後再試。";
        list.appendChild(message);
    }
}

// ==============================
// 學生課後評價：展開式表單開啟與關閉
// ==============================
const detailReviewModal = document.getElementById("detail-review-modal");
const detailReviewForm = document.getElementById("detail-review-form");
const detailReviewContent = document.getElementById("detail-review-content");
const detailReviewTitle = document.getElementById("detail-review-modal-title");
const detailReviewSubmit = document.getElementById("detail-review-submit");
const detailReviewCount = document.getElementById("detail-review-character-count");
const detailReviewError = document.getElementById("detail-review-error");

// 目前操作模式：create / edit
let detailReviewMode = "create";
let detailEditingReviewId = null;

// 開啟評價視窗
function openDetailReviewModal(mode, reviewId = null, content = "") {
    if (!detailReviewModal) return;

    // 避免上一個編輯狀態殘留
    if (!detailReviewModal.hidden) {
        closeDetailReviewModal();
    }

    detailReviewMode = mode;
    detailEditingReviewId = reviewId;

    const isTeacherReply = mode === "reply" || mode === "reply-edit";
    const isEditing = mode === "edit" || mode === "reply-edit";

    detailReviewTitle.textContent = isTeacherReply
        ? (isEditing ? "編輯老師回覆" : "回覆學生評價")
        : (isEditing ? "編輯評價" : "撰寫評價");

    detailReviewSubmit.textContent = isEditing
        ? "儲存修改"
        : (isTeacherReply ? "送出回覆" : "送出評價");

    detailReviewContent.value = isEditing ? content : "";
    detailReviewCount.textContent = detailReviewContent.value.length;

    detailReviewError.textContent = "";
    detailReviewError.hidden = true;

    const reviewCard = document.querySelector(
        `.detail-review-item[data-review-id="${reviewId}"]`
    );

    const reviewGroup = reviewCard?.closest(".detail-review-group");

    const editorHeader = detailReviewModal.querySelector(
        ".detail-review-editor-header"
    );

    if (isEditing && reviewCard) {
        const targetContent = isTeacherReply
            ? reviewGroup?.querySelector(".detail-review-reply-content")
            : reviewCard.querySelector(".detail-review-content-display");

        const targetActions = isTeacherReply
            ? reviewGroup?.querySelector(
                ".detail-review-reply .detail-review-actions"
            )
            : reviewCard.querySelector(".detail-review-actions");

        if (targetContent) {
            targetContent.hidden = true;
            targetContent.after(detailReviewModal);
        }

        if (targetActions) {
            targetActions.hidden = true;
        }

        if (editorHeader) {
            editorHeader.hidden = true;
        }
    } else if (isTeacherReply && reviewGroup) {
        // 第一次回覆：在學生評價下方開啟表單
        reviewGroup.appendChild(detailReviewModal);

        const replyActions = reviewGroup.querySelector(
            ":scope > .detail-review-actions"
        );

        if (replyActions) {
            replyActions.hidden = true;
        }

        if (editorHeader) {
            editorHeader.hidden = false;
        }
    } else {
        const reviewList = document.getElementById("detail-reviews-list");

        if (reviewList) {
            reviewList.before(detailReviewModal);
        }

        if (editorHeader) {
            editorHeader.hidden = false;
        }
    }

    detailReviewModal.hidden = false;
    detailReviewContent.focus();

    if (window.lucide) {
        lucide.createIcons();
    }
}

// 關閉評價視窗
function closeDetailReviewModal() {
    if (!detailReviewModal || detailReviewSubmit?.disabled) return;

    const editingGroup = detailReviewModal.closest(".detail-review-group");
    const editingCard = detailReviewModal.closest(".detail-review-item");

    if (editingGroup) {
        const studentContent = editingGroup.querySelector(
            ".detail-review-content-display"
        );

        const teacherContent = editingGroup.querySelector(
            ".detail-review-reply-content"
        );

        const actions = editingGroup.querySelectorAll(
            ".detail-review-actions"
        );

        if (studentContent) {
            studentContent.hidden = false;
        }

        if (teacherContent) {
            teacherContent.hidden = false;
        }

        actions.forEach(function (action) {
            action.hidden = false;
        });
    } else if (editingCard) {
        const reviewContent = editingCard.querySelector(
            ".detail-review-content-display"
        );

        if (reviewContent) {
            reviewContent.hidden = false;
        }
    }

    detailReviewModal.hidden = true;
    detailReviewForm?.reset();

    const reviewList = document.getElementById("detail-reviews-list");

    if (reviewList) {
        reviewList.before(detailReviewModal);
    }

    detailReviewMode = "create";
    detailEditingReviewId = null;
}

// 點擊右上角 X
document.getElementById("detail-review-modal-close")
    ?.addEventListener("click", closeDetailReviewModal);

// 點擊取消
document.getElementById("detail-review-cancel")
    ?.addEventListener("click", closeDetailReviewModal);

// 按下 Escape 關閉
document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && detailReviewModal && !detailReviewModal.hidden) {
        closeDetailReviewModal();
    }
});

// 即時更新字數
detailReviewContent?.addEventListener("input", function () {
    detailReviewCount.textContent = detailReviewContent.value.length;
});

// ==============================
// 學生課後評價：新增與編輯
// ==============================
detailReviewForm?.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (detailReviewSubmit.disabled) return;

    const content = detailReviewContent.value.trim();
    const token = sessionStorage.getItem("tutorlink_token");

    const isTeacherReply = (
        detailReviewMode === "reply" ||
        detailReviewMode === "reply-edit"
    );

    // 清除前一次錯誤
    detailReviewError.textContent = "";
    detailReviewError.hidden = true;

    if (!token) {
        detailReviewError.textContent = "請先登入會員。";
        detailReviewError.hidden = false;
        return;
    }

    if (!content || content.length > 200) {
        detailReviewError.textContent = isTeacherReply
            ? "請輸入 1～200 字的回覆內容。"
            : "請輸入 1～200 字的評價內容。";
        detailReviewError.hidden = false;
        return;
    }

    const isEditing = (
        detailReviewMode === "edit" ||
        detailReviewMode === "reply-edit"
    );

    const currentTeacherId = teacherId;

    if (!currentTeacherId || !/^[1-9]\d*$/.test(currentTeacherId)) {
        detailReviewError.textContent = "老師資料不正確，請重新整理頁面。";
        detailReviewError.hidden = false;
        return;
    }

    if (isEditing && !detailEditingReviewId) {
        detailReviewError.textContent = "找不到要編輯的評價。";
        detailReviewError.hidden = false;
        return;
    }

    const originalText = detailReviewSubmit.textContent;
    detailReviewSubmit.disabled = true;
    detailReviewSubmit.textContent = "處理中...";

    try {
        let url;
        let method;
        let body;

        if (isTeacherReply) {
            // 老師首次回覆或修改回覆，使用同一支 API
            url = `/api/reviews/${encodeURIComponent(detailEditingReviewId)}/reply`;
            method = "PATCH";
            body = { content };

        } else if (isEditing) {
            // 學生修改自己的評價
            url = `/api/reviews/${encodeURIComponent(detailEditingReviewId)}`;
            method = "PATCH";
            body = { content };

        } else {
            // 查詢已完成課程，取得可評價的預約 ID
            const status = await getMyTeacherReviewStatus(currentTeacherId);

            if (!status?.eligible || status.hasReview || !status.bookingId) {
                throw new Error("目前沒有可評價的已完成課程。");
            }

            url = "/api/reviews";
            method = "POST";
            body = {
                booking_id: status.bookingId,
                content
            };
        }

        // 避免切換帳號後使用舊憑證送出
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            throw new Error("會員登入狀態已改變，請重新操作。");
        }

        const response = await fetch(url, {
            method,
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const detail = errorData.detail;

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : isEditing
                        ? "修改評價失敗，請稍後再試。"
                        : "送出評價失敗，請稍後再試。"
            );
        }

        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        // 成功後關閉表單並重新載入評價
        detailReviewSubmit.disabled = false;
        closeDetailReviewModal();

        await loadTeacherReviews(currentTeacherId);

    } catch (error) {
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        console.error("儲存學生評價失敗：", error);
        detailReviewError.textContent = error.message;
        detailReviewError.hidden = false;

    } finally {
        detailReviewSubmit.disabled = false;
        detailReviewSubmit.textContent = originalText;
    }
});


window.addEventListener("load", () => {
    if (
        window.location.hash !== "#detail-reviews-section" ||
        new URLSearchParams(window.location.search).has("review_id")
    ) {
        return;
    }

    const reviewsSection = document.getElementById(
        "detail-reviews-section"
    );

    if (!reviewsSection) return;

    setTimeout(() => {
        reviewsSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }, 500);
});
