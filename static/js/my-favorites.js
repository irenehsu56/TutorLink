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
// 我的收藏老師
// ==============================

// 取得頁面元素
const favoritesLoading = document.getElementById("favorites-loading");
const favoritesList = document.getElementById("favorites-list");
const favoritesEmpty = document.getElementById("favorites-empty");
const favoritesLoginRequired = document.getElementById("favorites-login-required");
const favoritesLoginButton = document.getElementById("favorites-login-button");

// 將收藏老師資料顯示成卡片
function renderFavoriteTeachers(teachers) {
    favoritesList.innerHTML = "";

    teachers.forEach(function (teacher) {
        const card = document.createElement("article");

        // 將老師的多個教學地區整理成顯示文字
        const locationText = (teacher.locations || [])
            .map(function (location) {
                return `${location.city}・${location.district}`;
            })
            .join("、") || "尚未設定教學地區";

        // 根據老師性別設定預設頭像樣式
        let avatarGenderClass = "";

        if (teacher.gender === "男" || teacher.gender === "male") {
            avatarGenderClass = "male";
        } else if (teacher.gender === "女" || teacher.gender === "female") {
            avatarGenderClass = "female";
        }

        card.className = "teacher-card favorite-teacher-card";

        card.innerHTML = `
            <!-- 取消收藏按鈕 -->
            <button
                type="button"
                class="favorite-heart-button"
                aria-label="取消收藏老師"
                title="取消收藏"
                disabled
            >
                <i data-lucide="heart"></i>
            </button>

            <div class="teacher-card-header">
                <div class="teacher-avatar ${avatarGenderClass}">
                    ${teacher.photo_url
                        ? `
                            <img
                                src="${teacher.photo_url}"
                                alt="老師頭貼"
                                class="teacher-avatar-image"
                                referrerpolicy="no-referrer"
                            >
                        `
                        : `
                            <i data-lucide="user-round"></i>
                        `
                    }
                </div>

                <div class="teacher-basic">
                    <h3>${teacher.name}</h3>
                    <p>${locationText}</p>
                </div>
            </div>

            <div class="teacher-tags">
                ${(teacher.subjects || []).map(function (subject) {
                    const subjectName = subjectNameMap[subject] ?? subject;
                    return `<span class="teacher-tag">${subjectName}</span>`;
                }).join("")}

                <span class="teacher-grade">
                    ${(teacher.grades || []).map(function (grade) {
                        return gradeNameMap[grade] ?? grade;
                    }).join("、")}
                </span>
            </div>

            <p class="teacher-education">
                <i data-lucide="graduation-cap"></i>
                ${teacher.education}
            </p>

            <p class="teacher-experience">
                <i data-lucide="award"></i>
                ${teacher.experience} 年教學經驗
            </p>

            <p class="teacher-intro">
                ${teacher.intro}
            </p>

            <div class="teacher-card-footer">
                <p class="teacher-price">
                    NT$ ${teacher.hourlyRate}
                    <span>/ 小時</span>
                </p>

                <button type="button" class="teacher-detail-button">
                    查看老師
                    <i data-lucide="arrow-right"></i>
                </button>
            </div>
        `;

        // 查看老師詳細資料
        const detailButton = card.querySelector(".teacher-detail-button");

        detailButton.addEventListener("click", function () {
            window.location.href = `/teacher-detail.html?id=${teacher.id}`;
        });

        // 取消收藏老師
        const heartButton = card.querySelector(".favorite-heart-button");

        // 啟用愛心按鈕
        heartButton.disabled = false;

        heartButton.addEventListener("click", function () {
            removeFavoriteTeacher(teacher.id, card);
        });

        favoritesList.appendChild(card);
    });

    // 將動態產生的圖示轉成 Lucide SVG
    lucide.createIcons();
}

// 讀取目前會員的收藏老師
async function loadMyFavorites() {
    favoritesList.innerHTML = "";
    favoritesEmpty.hidden = true;

    // 沿用會員登入時儲存的 JWT
    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入時顯示登入提示卡片
    if (!token) {
        favoritesLoading.hidden = true;
        favoritesLoginRequired.hidden = false;
        document.body.classList.add("favorites-login-required");
        return;
    }

    // 已登入時隱藏登入提示卡片
    favoritesLoginRequired.hidden = true;
    document.body.classList.remove("favorites-login-required");

    // 顯示載入中提示
    favoritesLoading.textContent = "正在載入收藏老師...";
    favoritesLoading.hidden = false;

    try {
        const response = await fetch("/api/favorites", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("無法取得收藏老師清單");
        }

        const data = await response.json();

        // 登入憑證已改變時，不顯示舊會員的收藏資料
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        favoritesLoading.hidden = true;

        if (data.teachers.length === 0) {
            favoritesEmpty.hidden = false;
            lucide.createIcons();
            return;
        }

        // 將收藏老師資料顯示成卡片
        renderFavoriteTeachers(data.teachers);

    } catch (error) {
        console.error("讀取收藏老師失敗：", error);
        favoritesLoading.textContent = "讀取收藏老師失敗，請稍後再試。";
    }
}

// ==============================
// 取消收藏老師
// ==============================

async function removeFavoriteTeacher(teacherId, card) {
    const token = sessionStorage.getItem("tutorlink_token");
    const heartButton = card.querySelector(".favorite-heart-button");

    if (!token || !heartButton) {
        return;
    }

    heartButton.disabled = true;

    try {
        const response = await fetch(`/api/favorites/${teacherId}`, {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("取消收藏失敗");
        }

        // 成功後移除卡片
        card.remove();

        // 重新取得收藏清單，更新數量與空狀態
        await loadMyFavorites();

    } catch (error) {
        console.error("取消收藏老師失敗：", error);
        alert("取消收藏失敗，請稍後再試");

        heartButton.disabled = false;
    }
}

// 頁面載入後取得收藏資料
loadMyFavorites();

// ==============================
// 會員登入後載入收藏清單
// ==============================

window.addEventListener("tutorlink:login", function () {

    // 清除先前的提示文字
    favoritesLoading.textContent = "正在載入收藏老師...";

    // 重新讀取目前登入會員的收藏資料
    loadMyFavorites();
});

// ==============================
// 會員登出後顯示登入提示
// ==============================

window.addEventListener("tutorlink:logout", function () {
    // 重新檢查登入狀態並清空收藏清單
    loadMyFavorites();
});

// ==============================
// 未登入提示：開啟會員登入視窗
// ==============================

favoritesLoginButton.addEventListener("click", function () {
    openAuthModal("login");
});