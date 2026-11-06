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

// 讀取首頁傳來的搜尋條件
const urlParams = new URLSearchParams(window.location.search);

// ==============================
// Location 地區選擇功能
// ==============================

// 取得地區選單相關 HTML 元素
const locationTrigger = document.getElementById("location-trigger");
const locationDropdown = document.getElementById("location-dropdown");
const locationText = document.getElementById("location-text");

const locationSelect = document.getElementById("location");
const districtSelect = document.getElementById("district");
const locationField = document.querySelector(".location-field");

// 更新地區欄位顯示的文字
function updateLocationText() {
    // 取得選擇的縣市中文名稱
    const cityName = locationSelect.value
        ? locationSelect.options[locationSelect.selectedIndex].text
        : "";

    // 取得行政區名稱
    const districtName = districtSelect.value;

    if (!cityName) {
        // 沒選縣市
        locationText.textContent = "請選擇地區";
    } else if (!districtName) {
        // 只選縣市
        locationText.textContent = cityName;
    } else {
        // 縣市和行政區都有選
        locationText.textContent = `${cityName}・${districtName}`;
    }
}

// 點擊地區欄位，展開或收起選單
locationTrigger.addEventListener("click", function () {
    const isOpen = !locationDropdown.hidden;

    locationDropdown.hidden = isOpen;
    locationTrigger.setAttribute("aria-expanded", String(!isOpen));
});

// 等待行政區資料載入完成
// 讀取縣市對應的行政區 JSON
const districtsReady = fetch("/static/data/districts.json")
    .then(function (response) {
        if (!response.ok) {
            throw new Error("行政區資料讀取失敗");
        }

        return response.json();
    })
    .then(function (districtData) {

        // 使用者更換縣市時
        locationSelect.addEventListener("change", function () {
            const selectedCity = locationSelect.value;

            // 清除原本的行政區選項
            districtSelect.innerHTML =
                '<option value="">請先選擇縣市</option>';

            districtSelect.disabled = true;

            // 未選縣市時，恢復不限制地區
            if (!selectedCity || !districtData[selectedCity]) {
                updateLocationText();
                return;
            }

            // 已選縣市，但不一定要選行政區
            districtSelect.innerHTML =
                '<option value="">全部行政區</option>';

            districtSelect.disabled = false;

            // 根據縣市產生行政區選項
            const districts = districtData[selectedCity];

            districts.forEach(function (district) {
                const option = document.createElement("option");

                option.value = district;
                option.textContent = district;

                districtSelect.appendChild(option);
            });

            // 選擇縣市後立即更新顯示文字
            updateLocationText();
        });

        // 使用者更換行政區時，立即更新顯示文字
        districtSelect.addEventListener("change", function () {
            updateLocationText();
        });
    })
    .catch(function (error) {
        console.error("載入行政區資料失敗：", error);
        throw error;
    });

// 點擊地區選單外面時，自動收起
document.addEventListener("click", function (event) {
    if (!locationField.contains(event.target)) {
        locationDropdown.hidden = true;
        locationTrigger.setAttribute("aria-expanded", "false");
    }
});

// ==============================
// Teachers 老師資料與卡片
// ==============================

// 儲存從 JSON 取得的全部老師資料，供搜尋篩選使用
let allTeachers = [];

// 儲存目前會員已收藏的老師 ID
let favoriteTeacherIds = new Set();

// 讀取目前會員的收藏老師
async function loadTeacherFavorites() {
    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入時不需要查詢
    if (!token) {
        favoriteTeacherIds.clear();
        return;
    }

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

        // 將已收藏的老師 ID 儲存起來
        favoriteTeacherIds = new Set(
            data.teachers.map(function (teacher) {
                return Number(teacher.id);
            })
        );

    } catch (error) {
        console.error("讀取老師收藏狀態失敗：", error);
    }
}

// 老師資料載入狀態：loading（載入中）、success（成功）、error（失敗）
let teachersStatus = "loading";

// 取得老師列表與搜尋結果數量的 HTML 元素
const teacherList = document.getElementById("teacher-list");
const resultCount = document.getElementById("result-count");

// 取得排序選單
const sortOrder = document.getElementById("sort-order");

// 儲存目前搜尋結果
let currentTeachers = [];

// 等待老師資料載入完成
// 透過 FastAPI 從 MySQL 取得老師資料
const teachersReady = fetch("/api/teachers")
    .then(function (response) {
        if (!response.ok) {
            throw new Error("老師資料讀取失敗");
        }

        return response.json();
    })
    .then(async function (teachers) {
        // 將取得的老師資料儲存起來
        allTeachers = teachers;

        // 先讀取會員收藏狀態
        await loadTeacherFavorites();

        // 標記老師資料載入成功
        teachersStatus = "success";

        // 初次載入頁面時，顯示全部老師
        renderTeachers(allTeachers);
    })
    .catch(function (error) {
        console.error("載入老師資料失敗：", error);

        // 標記老師資料載入失敗
        teachersStatus = "error";

        resultCount.textContent = "無法載入老師資料";
        teacherList.textContent = "老師資料載入失敗，請重新整理頁面後再試。";
    });

// 將老師資料顯示成卡片
function renderTeachers(teachers) {
    // 記錄目前的搜尋結果
    currentTeachers = [...teachers];

    // 複製資料，避免修改原本的老師順序
    const sortedTeachers = [...teachers];

    // 根據使用者選擇的方式排序
    if (sortOrder.value === "price-low") {
        sortedTeachers.sort(function (a, b) {
            return a.hourlyRate - b.hourlyRate;
        });
    } else if (sortOrder.value === "price-high") {
        sortedTeachers.sort(function (a, b) {
            return b.hourlyRate - a.hourlyRate;
        });
    }

    teacherList.innerHTML = "";

    // 更新搜尋結果數量
    resultCount.textContent = `共找到 ${teachers.length} 位老師`;

    if (teachers.length === 0) {
        teacherList.innerHTML = `
            <p class="no-results">
                目前沒有符合條件的老師，請嘗試其他搜尋條件。
            </p>
        `;
        return;
    }

    sortedTeachers.forEach(function (teacher) {
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

        card.className = "teacher-card teacher-favorite-card";

        card.innerHTML = `
            <!-- 收藏老師按鈕 -->
            <button
                type="button"
                class="teacher-heart-button ${favoriteTeacherIds.has(Number(teacher.id)) ? "is-favorited" : ""}"
                ${sessionStorage.getItem("tutorlink_token") ? "" : "hidden"}
                aria-label="${favoriteTeacherIds.has(Number(teacher.id)) ? "已收藏老師" : "收藏老師"}"
                title="${favoriteTeacherIds.has(Number(teacher.id)) ? "已收藏" : "收藏老師"}"
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
                ${teacher.subjects.map(function (subject) {

                    // 將英文科目代碼轉成中文
                    // 原本就是中文時，維持原本的名稱
                    const subjectName = subjectNameMap[subject] ?? subject;

                    return `<span class="teacher-tag">${subjectName}</span>`;

                }).join("")}

                <span class="teacher-grade">
                    ${teacher.grades.map(function (grade) {

                        // 將英文年級代碼轉成中文
                        // 原本就是中文時，維持原本的名稱
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
        // 取得目前這張老師卡片的「查看老師」按鈕
        const detailButton = card.querySelector(".teacher-detail-button");

        // 點擊後，帶著老師 ID 跳轉至詳細介紹頁面
        detailButton.addEventListener("click", function () {
            window.location.href = `/teacher-detail.html?id=${teacher.id}`;
        });

        // 收藏老師／取消收藏老師
        const heartButton = card.querySelector(".teacher-heart-button");

        // 啟用愛心按鈕
        heartButton.disabled = false;

        // 點擊愛心後切換收藏狀態
        heartButton.addEventListener("click", function () {
            toggleTeacherFavorite(teacher.id, heartButton);
        });

        teacherList.appendChild(card);
    });

    // 將動態產生的圖示轉成 Lucide SVG
    lucide.createIcons();
}

// ==============================
// 收藏老師／取消收藏老師
// ==============================

async function toggleTeacherFavorite(teacherId, heartButton) {
    const token = sessionStorage.getItem("tutorlink_token");

    // 未登入時提示登入
    if (!token) {
        alert("請先登入會員，才能收藏老師");
        return;
    }

    // 避免重複點擊
    heartButton.disabled = true;

    // 根據目前收藏狀態決定 API 方法
    const isFavorited = favoriteTeacherIds.has(Number(teacherId));
    const method = isFavorited ? "DELETE" : "POST";

    try {
        const response = await fetch(`/api/favorites/${teacherId}`, {
            method: method,
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("收藏操作失敗");
        }

        // 更新目前會員的收藏老師 ID
        if (isFavorited) {
            favoriteTeacherIds.delete(Number(teacherId));
        } else {
            favoriteTeacherIds.add(Number(teacherId));
        }

        // 更新愛心外觀
        const newIsFavorited = favoriteTeacherIds.has(Number(teacherId));

        heartButton.classList.toggle("is-favorited", newIsFavorited);
        heartButton.setAttribute(
            "aria-label",
            newIsFavorited ? "已收藏老師" : "收藏老師"
        );
        heartButton.title = newIsFavorited ? "已收藏" : "收藏老師";

    } catch (error) {
        console.error("收藏老師操作失敗：", error);
        alert("收藏操作失敗，請稍後再試");

    } finally {
        heartButton.disabled = false;
    }
}

// ==============================
// Search 老師搜尋功能
// ==============================

// HTML 科目代碼與 JSON 中文科目的對照表
const subjectMap = {
    math: "數學",
    english: "英文",
    chinese: "國文",
    science: "自然",
    social: "社會",
    art: "美術",
    music: "音樂",
    other: "其他"
};

// HTML 年級代碼與 JSON 中文年級的對照表
const gradeMap = {
    elementary: "國小",
    junior: "國中",
    senior: "高中"
};

// 取得搜尋表單、科目選單與年級選單
const searchForm = document.getElementById("search");
const subjectSelect = document.getElementById("subject");
const gradeSelect = document.getElementById("grade");

// 使用者點擊「搜尋家教老師」時執行
searchForm.addEventListener("submit", function (event) {
    // 阻止表單預設送出，避免頁面重新整理
    event.preventDefault();

    // 老師資料尚未載入成功時，不執行搜尋
    if (teachersStatus === "loading") {
        alert("老師資料正在載入中，請稍後再試");
        return;
    }

    if (teachersStatus === "error") {
        alert("老師資料載入失敗，請重新整理頁面後再試");
        return;
    }

    // 取得使用者選擇的科目，並轉換成中文
    const selectedSubject = subjectMap[subjectSelect.value];

    // 取得使用者選擇的年級，並轉換成中文
    const selectedGrade = gradeMap[gradeSelect.value];

    // 取得使用者選擇的縣市中文名稱
    const selectedCity = locationSelect.value
        ? locationSelect.options[locationSelect.selectedIndex].text
        : "";

    // 取得使用者選擇的行政區
    const selectedDistrict = districtSelect.value;

    // 從全部老師資料中，篩選符合條件的老師
    const filteredTeachers = allTeachers.filter(function (teacher) {
        // 同時支援英文代碼與中文科目名稱
        const matchSubject = !selectedSubject ||
            teacher.subjects.some(function (subject) {
                return (subjectNameMap[subject] ?? subject) === selectedSubject;
            });

        // 地區：必須由同一筆教學地區同時符合縣市與行政區
        const matchLocation = (!selectedCity && !selectedDistrict) ||
            (teacher.locations || []).some(function (location) {
                const matchCity = !selectedCity ||
                    location.city === selectedCity;

                const matchDistrict = !selectedDistrict ||
                    location.district === selectedDistrict;

                return matchCity && matchDistrict;
            });

        // 同時支援英文代碼與中文年級名稱
        const matchGrade = !selectedGrade ||
            teacher.grades.some(function (grade) {
                return (gradeNameMap[grade] ?? grade) === selectedGrade;
            });

        // 科目、地區、年級都符合，才保留這位老師
        return matchSubject && matchLocation && matchGrade;
    });

    // 顯示篩選後的老師卡片
    renderTeachers(filteredTeachers);
});
 
// ==============================
// URL 接收首頁搜尋條件
// ==============================

// 等待行政區與老師資料都載入完成
Promise.all([districtsReady, teachersReady]).then(function () {

    // 如果老師資料載入失敗，就不執行搜尋
    if (teachersStatus !== "success") {
        return;
    }

    // 取得首頁傳來的搜尋條件
    const subject = urlParams.get("subject") || "";
    const city = urlParams.get("city") || "";
    const district = urlParams.get("district") || "";
    const grade = urlParams.get("grade") || "";

    // 沒有搜尋條件時，維持顯示全部老師
    if (!subject && !city && !district && !grade) {
        return;
    }

    // 設定科目與年級
    subjectSelect.value = subject;
    gradeSelect.value = grade;

    // 設定縣市與行政區
    if (city) {
        locationSelect.value = city;

        // 觸發縣市變更事件，產生對應行政區選項
        locationSelect.dispatchEvent(new Event("change"));

        if (district) {
            districtSelect.value = district;
            updateLocationText();
        }
    }

    // 自動執行老師搜尋
    searchForm.requestSubmit();
}).catch(function (error) {
    console.error("無法套用首頁搜尋條件：", error);
});

// ==============================
// Sort 老師排序功能
// ==============================

// 切換排序方式時，重新顯示目前的搜尋結果
sortOrder.addEventListener("change", function () {
    if (teachersStatus !== "success") {
        return;
    }

    renderTeachers(currentTeachers);
});

// ==============================
// 會員登入／登出後更新收藏愛心
// ==============================

// 登入成功：重新讀取收藏資料並更新愛心
window.addEventListener("tutorlink:login", async function () {
    await loadTeacherFavorites();

    if (teachersStatus === "success") {
        renderTeachers(currentTeachers);
    }
});

// 登出成功：清除收藏資料並隱藏愛心
window.addEventListener("tutorlink:logout", function () {
    favoriteTeacherIds.clear();

    if (teachersStatus === "success") {
        renderTeachers(currentTeachers);
    }
});

// ==============================
// 返回老師列表時更新收藏狀態
// ==============================

window.addEventListener("pageshow", async function (event) {

    // 只有從瀏覽器上一頁快取恢復時才重新查詢
    if (!event.persisted) {
        return;
    }

    // 重新讀取目前會員的收藏資料
    await loadTeacherFavorites();

    // 保留目前的搜尋結果與排序，更新卡片愛心
    if (teachersStatus === "success") {
        renderTeachers(currentTeachers);
    }
});