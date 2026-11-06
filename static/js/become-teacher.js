if (window.lucide) {lucide.createIcons();}

// ==============================
// Teacher Profile 老師個人資料管理
// ==============================
// 記錄目前是否已經建立老師資料
let currentTeacherProfile = null;

// ==============================
// 判斷是否從「編輯資料」按鈕進入
// ==============================
const teacherPageParams = new URLSearchParams(
    window.location.search
);

const isTeacherEditPage =
    teacherPageParams.get("mode") === "edit";

 // ==============================
 // 進入成為家教頁面時，確認登入狀態
 // ==============================
async function checkTeacherPageLogin() {
    const token = sessionStorage.getItem("tutorlink_token");

    function requireLogin() {
        document.body.classList.add("teacher-login-required");

        // 避免重複建立通知
        if (document.getElementById("teacher-login-notice")) {
            return;
        }

        const notice = document.createElement("div");
        notice.id = "teacher-login-notice";
        notice.className = "teacher-login-notice";

        notice.innerHTML = `
            <div class="teacher-login-card">
                <div class="teacher-login-icon">
                    <i data-lucide="lock-keyhole"></i>
                </div>

                <h2>請先登入會員</h2>

                <p>
                    登入 TutorLink 後，即可建立個人教學檔案，
                    開始你的家教之旅！
                </p>

                <button type="button" id="teacher-login-button">
                    立即登入
                </button>
            </div>
        `;

        document.body.appendChild(notice);
        lucide.createIcons();

        document.getElementById("teacher-login-button")
            .addEventListener("click", function () {
                openAuthModal("login");
            });
    }

    if (!token) {
        requireLogin();
        return false;
    }

    try {
        const response = await fetch("/api/auth/me", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (response.status === 401 || response.status === 403) {
            sessionStorage.removeItem("tutorlink_token");
            requireLogin();
            return false;
        }

        if (!response.ok) {
            console.error("登入驗證失敗：", response.status);
            return false;
        }

        document.body.classList.remove("teacher-login-required");
        document.getElementById("teacher-login-notice")?.remove();

        return true;

    } catch (error) {
        console.error("登入驗證失敗：", error);
        return false;
    }
}


// ==============================
// 會員登出時，清除目前老師資料
// ==============================
window.addEventListener("tutorlink:logout", function () {

    // 清除老師資料，避免切換帳號後沿用舊狀態
    currentTeacherProfile = null;

});

// ==============================
// 取得目前登入會員的老師資料
// ==============================
async function loadMyTeacherProfile(shouldRedirect = true) {

    // 取得登入憑證
    const token = sessionStorage.getItem("tutorlink_token");

    // 尚未登入，不查詢老師資料
    if (!token) {
        return;
    }

    try {
        const response = await fetch("/api/teachers/me", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        // 404：尚未建立老師資料，維持新增模式
        if (response.status === 404) {
            currentTeacherProfile = null;
            return;
        }

        // 其他錯誤
        if (!response.ok) {
            console.error("取得老師資料失敗：", response.status);
            return;
        }

        const data = await response.json();

        // 儲存目前老師資料
        currentTeacherProfile = data.teacher;

        // 已經有老師資料，而且不是從編輯按鈕進入
        // 直接前往自己的老師詳細介紹頁面
        if (
            currentTeacherProfile?.id &&
            !isTeacherEditPage &&
            shouldRedirect
        ) {
            window.location.replace(
                `/teacher-detail.html?id=${currentTeacherProfile.id}`
            );

            return;
        }

        // 顯示 AWS S3 已儲存的老師頭貼
        // 取得頭貼圖片與相機圖示
        const photoImage = document.getElementById("teacher-photo-image");
        const photoIcon = document.getElementById("teacher-photo-icon");

        // 清除本機預覽照片的載入事件
        // 避免讀取 AWS S3 照片時觸發舊的預覽事件
        photoImage.onload = null;
        photoImage.onerror = null;

        // 如果老師已有頭貼網址
        if (data.teacher.photo_url) {

            // 將 S3 的暫時讀取網址設定為圖片來源
            photoImage.src = data.teacher.photo_url;

            // 顯示頭貼，隱藏相機圖示
            photoImage.hidden = false;
            photoIcon.hidden = true;

        } else {

            // 沒有頭貼時，顯示預設相機圖示
            photoImage.removeAttribute("src");
            photoImage.hidden = true;
            photoIcon.hidden = false;
        }

        // 自動填入基本資料
        document.getElementById("teacher-name").value =
            data.teacher.name ?? "";

        document.getElementById("teacher-gender").value =
            data.teacher.gender ?? "";

        document.getElementById("teacher-education").value =
            data.teacher.education ?? "";

        document.getElementById("teacher-hourly-rate").value =
            data.teacher.hourlyRate ?? "";

        document.getElementById("teacher-experience").value =
            data.teacher.experience ?? "";

        document.getElementById("teacher-introduction").value =
            data.teacher.intro ?? "";

        // 自動勾選已儲存的教學科目與年級
        // 分別處理教學科目、教學年級
        [
            ["teacher-subjects", data.teacher.subjects],
            ["teacher-grades", data.teacher.grades]
        ].forEach(function ([containerId, savedValues]) {

            const container = document.getElementById(containerId);

            // 取得該欄位所有選項
            const checkboxes = container.querySelectorAll(
                'input[type="checkbox"]'
            );

            checkboxes.forEach(function (checkbox) {

                // 根據資料庫的值恢復勾選狀態
                checkbox.checked = (savedValues ?? []).includes(checkbox.value);

            });

            // 更新自訂複選選單的顯示文字
            container.dispatchEvent(
                new Event("change", { bubbles: true })
            );

        });

        // 自動載入每週可授課時段
        // 取得所有授課時段 checkbox
        const availabilityCheckboxes = document.querySelectorAll(
            '#teacher-availability input[type="checkbox"][name="availability"]'
        );

        // 從資料庫取得老師已儲存的授課時段
        const savedAvailability = data.teacher.availability ?? [];

        availabilityCheckboxes.forEach(function (checkbox) {

            // 例如 checkbox.value = "1-evening"
            const [day, period] = checkbox.value.split("-");

            // 前端星期日可能使用 0，後端則使用 7
            const normalizedDay = Number(day) === 0 ? 7 : Number(day);

            // 判斷這個時段是否存在於資料庫
            checkbox.checked = savedAvailability.some(function (item) {
                return Number(item.day) === normalizedDay &&
                    item.period === period;
            });

        });

        // 通知授課時段元件更新畫面
        document.getElementById("teacher-availability").dispatchEvent(
            new Event("change", { bubbles: true })
        );

        // 自動載入老師已儲存的教學地區
        window.setTeacherSelectedLocations(
            data.teacher.locations ?? []
        );

        // 通知其他表單元件：資料已載入
        document.getElementById("teacher-experience")
            .dispatchEvent(new Event("input", { bubbles: true }));

        console.log("已載入老師資料：", data.teacher);

    } catch (error) {
        console.error("載入老師資料時發生錯誤：", error);
    }
}

// ==============================
// Photo 老師頭貼上傳與即時預覽
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    // 取得頭貼上傳欄位及預覽元素
    const photoInput = document.getElementById("teacher-photo");
    const photoImage = document.getElementById("teacher-photo-image");
    const photoIcon = document.getElementById("teacher-photo-icon");

    // 限制圖片大小為 5 MB
    const maxFileSize = 5 * 1024 * 1024;

    // 允許的圖片格式
    const allowedTypes = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ];

    // 記錄目前預覽圖片的網址
    let currentPhotoURL = null;

    // 清除本機頭貼預覽網址
    function clearLocalPhotoPreview() {

        // 取消先前的圖片載入事件
        photoImage.onload = null;
        photoImage.onerror = null;

        // 釋放先前建立的本機圖片網址
        if (currentPhotoURL) {
            URL.revokeObjectURL(currentPhotoURL);
            currentPhotoURL = null;
        }
    }

    // 會員登出時，清除頭貼預覽與圖片網址
    window.addEventListener("tutorlink:logout", function () {

        // 停止舊圖片載入完成後更新畫面
        photoImage.onload = null;
        photoImage.onerror = null;

        // 釋放圖片預覽網址
        if (currentPhotoURL) {
            URL.revokeObjectURL(currentPhotoURL);
            currentPhotoURL = null;
        }

        // 清除上傳檔案與預覽
        photoInput.value = "";
        photoImage.removeAttribute("src");
        photoImage.hidden = true;
        photoIcon.hidden = false;

    });

    // 使用者選擇照片時
    photoInput.addEventListener("change", function () {

        const file = photoInput.files[0];

        // 沒有選擇檔案就不處理
        if (!file) {
            return;
        }

        // 檢查圖片格式
        if (!allowedTypes.includes(file.type)) {
            alert("請上傳 JPG、PNG 或 WebP 格式的圖片");
            photoInput.value = "";
            return;
        }

        // 檢查圖片大小
        if (file.size > maxFileSize) {
            alert("圖片大小不可超過 5 MB");
            photoInput.value = "";
            return;
        }

        // 清除前一次本機預覽使用的事件與網址
        clearLocalPhotoPreview();

        // 產生新的本機圖片預覽網址
        const newPhotoURL = URL.createObjectURL(file);

        // 記錄網址，方便下次釋放
        currentPhotoURL = newPhotoURL;

        // 圖片成功載入時
        photoImage.onload = function () {

            // 顯示照片並隱藏相機圖示
            photoImage.hidden = false;
            photoIcon.hidden = true;
        };

        // 圖片載入失敗時
        photoImage.onerror = function () {

            // 清除無法讀取的預覽網址
            clearLocalPhotoPreview();

            // 清除無效的檔案選擇
            photoInput.value = "";

            alert("圖片無法讀取，請重新選擇");
        };

        // 顯示使用者選擇的照片
        photoImage.src = newPhotoURL;
    });

});

// ==============================
// Location 老師教學地區：跨縣市複選
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    // 取得縣市選單、行政區複選選單及已選地區容器
    const citySelect = document.getElementById("teacher-city");
    const districtMultiselect = document.getElementById("teacher-districts");
    const districtTrigger = districtMultiselect.querySelector(".multiselect-trigger");
    const districtTriggerText = districtTrigger.querySelector("span");
    const districtOptions = document.getElementById("teacher-district-options");
    const selectedLocationsContainer = document.getElementById("teacher-selected-locations");

    // 儲存已選擇的所有教學地區
    // 每筆資料包含縣市代碼與行政區名稱
    const selectedLocations = [];

    // 會員登出時，清除已選擇的教學地區
    window.addEventListener("tutorlink:logout", function () {

        // 清空已選地區陣列
        selectedLocations.length = 0;

        // 清除畫面上的地區標籤
        selectedLocationsContainer.innerHTML = "";

        // 取消目前行政區選單的勾選
        districtOptions.querySelectorAll('input[type="checkbox"]').forEach(function (checkbox) {
            checkbox.checked = false;
        });

        // 恢復行政區選單的預設文字與狀態
        updateDistrictTrigger();

        // 收起行政區選單
        closeDistrictDropdown();

    });

    // 提供其他區塊取得已選擇的教學地區
    // 回傳複製的陣列，避免外部直接修改原始資料
    window.getTeacherSelectedLocations = function () {

        return selectedLocations.map(function (location) {
            return {
                city: location.city,
                district: location.district
            };
        });

    };

    // 提供其他區塊設定老師已儲存的教學地區
    window.setTeacherSelectedLocations = function (locations) {

        // 清空原本的教學地區
        selectedLocations.length = 0;

        // 將資料庫的縣市中文名稱轉換成前端代碼
        locations.forEach(function (location) {

            const cityOption = Array.from(citySelect.options).find(
                function (option) {
                    return option.textContent.trim() === location.city ||
                        option.value === location.city;
                }
            );

            // 找不到對應縣市就略過
            if (!cityOption) {
                console.warn("找不到對應的縣市：", location.city);
                return;
            }

            const city = cityOption.value;

            // 避免重複加入相同地區
            if (!isLocationSelected(city, location.district)) {
                selectedLocations.push({
                    city: city,
                    district: location.district
                });
            }

        });

        // 重新顯示已選擇的地區標籤
        renderSelectedLocations();

        // 更新行政區選單文字
        updateDistrictTrigger();

        // 同步目前縣市的 checkbox 勾選狀態
        districtOptions.querySelectorAll(
            'input[type="checkbox"]'
        ).forEach(function (checkbox) {

            checkbox.checked = isLocationSelected(
                citySelect.value,
                checkbox.value
            );

        });

    };

    // 取得縣市的中文名稱
    function getCityName(cityCode) {
        const option = Array.from(citySelect.options).find(function (item) {
            return item.value === cityCode;
        });

        return option ? option.textContent.trim() : cityCode;
    }

    // 檢查某個地區是否已經被選擇
    function isLocationSelected(city, district) {
        return selectedLocations.some(function (location) {
            return location.city === city && location.district === district;
        });
    }

    // 更新行政區按鈕顯示的文字
    function updateDistrictTrigger() {
        const city = citySelect.value;

        if (!city) {
            districtTriggerText.textContent = "請先選擇縣市";
            districtTrigger.disabled = true;
            return;
        }

        districtTrigger.disabled = false;

        // 計算目前縣市已選擇幾個行政區
        const count = selectedLocations.filter(function (location) {
            return location.city === city;
        }).length;

        districtTriggerText.textContent = count > 0
            ? `已選擇 ${count} 個行政區`
            : "請選擇行政區";
    }

    // 顯示所有已選擇的教學地區標籤
    function renderSelectedLocations() {
        selectedLocationsContainer.innerHTML = "";

        selectedLocations.forEach(function (location) {

            // 建立地區標籤
            const tag = document.createElement("div");
            tag.className = "teacher-location-tag";

            // 顯示縣市及行政區名稱
            const text = document.createElement("span");
            text.textContent =
                `${getCityName(location.city)}・${location.district}`;

            // 建立移除按鈕
            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "teacher-location-remove";
            removeButton.setAttribute(
                "aria-label",
                `移除 ${getCityName(location.city)}${location.district}`
            );
            removeButton.textContent = "×";

            // 點擊 ×，移除該地區
            removeButton.addEventListener("click", function () {

                const index = selectedLocations.findIndex(function (item) {
                    return item.city === location.city &&
                           item.district === location.district;
                });

                if (index !== -1) {
                    selectedLocations.splice(index, 1);
                }

                // 如果目前顯示的縣市相同，同步取消核取方塊
                if (citySelect.value === location.city) {
                    districtOptions.querySelectorAll(
                        'input[type="checkbox"]'
                    ).forEach(function (checkbox) {
                        if (checkbox.value === location.district) {
                            checkbox.checked = false;
                        }
                    });
                }

                renderSelectedLocations();
                updateDistrictTrigger();
            });

            tag.append(text, removeButton);
            selectedLocationsContainer.appendChild(tag);
        });
    }

    // 關閉行政區選單
    function closeDistrictDropdown() {
        districtOptions.hidden = true;
        districtTrigger.setAttribute("aria-expanded", "false");
    }

    // 從 districts.json 讀取行政區資料
    fetch("/static/data/districts.json")
        .then(function (response) {

            if (!response.ok) {
                throw new Error("行政區資料讀取失敗");
            }

            return response.json();
        })
        .then(function (districtData) {

            // 根據目前縣市，產生行政區核取方塊
            function renderDistrictOptions() {
                const city = citySelect.value;

                districtOptions.innerHTML = "";
                closeDistrictDropdown();

                if (!city || !districtData[city]) {
                    districtTrigger.disabled = true;
                    districtTriggerText.textContent = "請先選擇縣市";
                    return;
                }

                districtData[city].forEach(function (district) {

                    // 每個行政區使用一個 label
                    const label = document.createElement("label");

                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.value = district;

                    // 切換回之前的縣市時，恢復勾選狀態
                    checkbox.checked = isLocationSelected(city, district);

                    const name = document.createElement("span");
                    name.textContent = district;

                    // 勾選或取消勾選行政區
                    checkbox.addEventListener("change", function () {

                        const index = selectedLocations.findIndex(
                            function (location) {
                                return location.city === city &&
                                       location.district === district;
                            }
                        );

                        if (checkbox.checked && index === -1) {
                            selectedLocations.push({
                                city: city,
                                district: district
                            });
                        } else if (!checkbox.checked && index !== -1) {
                            selectedLocations.splice(index, 1);
                        }

                        renderSelectedLocations();
                        updateDistrictTrigger();
                    });

                    label.append(checkbox, name);
                    districtOptions.appendChild(label);
                });

                updateDistrictTrigger();
            }

            // 切換縣市時，更新行政區選項
            citySelect.addEventListener("change", renderDistrictOptions);

            // 初始化行政區選單
            renderDistrictOptions();
        })
        .catch(function (error) {
            console.error("載入行政區資料失敗：", error);
            districtTrigger.disabled = true;
            districtTriggerText.textContent = "行政區載入失敗";
        });

    // 點擊行政區按鈕，展開或收合選單
    districtTrigger.addEventListener("click", function () {
        const shouldOpen = districtOptions.hidden;

        districtOptions.hidden = !shouldOpen;
        districtTrigger.setAttribute(
            "aria-expanded",
            String(shouldOpen)
        );
    });

    // 點擊行政區選單外面，自動收起
    document.addEventListener("click", function (event) {
        if (!districtMultiselect.contains(event.target)) {
            closeDistrictDropdown();
        }
    });

    // 按下 Esc，收起行政區選單
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !districtOptions.hidden) {
            closeDistrictDropdown();
            districtTrigger.focus();
        }
    });

});

// ==============================
// Teaching 教學科目、教學年級複選
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    // 取得教學科目及教學年級的複選選單
    const teachingMultiselects = document.querySelectorAll(
        "#teacher-subjects, #teacher-grades"
    );

    // 關閉指定的複選選單
    function closeTeachingDropdown(multiselect) {
        const trigger = multiselect.querySelector(".multiselect-trigger");
        const options = multiselect.querySelector(".multiselect-options");

        options.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
    }

    // 更新按鈕上顯示的已選內容
    function updateTeachingText(multiselect) {
        const triggerText = multiselect.querySelector(
            ".multiselect-trigger span"
        );

        // 取得所有已勾選的核取方塊
        const checkedInputs = multiselect.querySelectorAll(
            '.multiselect-options input[type="checkbox"]:checked'
        );

        // 取得勾選選項的中文名稱
        const selectedNames = Array.from(checkedInputs).map(function (input) {
            return input.closest("label").textContent.trim();
        });

        // 沒有勾選時，顯示原本的提示文字
        if (selectedNames.length === 0) {
            triggerText.textContent =
                multiselect.id === "teacher-subjects"
                    ? "請選擇教學科目"
                    : "請選擇教學年級";

            return;
        }

        // 有勾選時，顯示所有選擇的內容
        triggerText.textContent = selectedNames.join("、");
    }

    // 表單重設後，更新教學科目與年級的顯示狀態
    const teacherForm = document.getElementById("teacher-application-form");

    teacherForm.addEventListener("reset", function () {

        requestAnimationFrame(function () {

            teachingMultiselects.forEach(function (multiselect) {

                // 恢復預設提示文字
                updateTeachingText(multiselect);

                // 收起複選選單
                closeTeachingDropdown(multiselect);

            });

        });

    });

    // 分別設定教學科目、教學年級的互動
    teachingMultiselects.forEach(function (multiselect) {

        const trigger = multiselect.querySelector(".multiselect-trigger");
        const options = multiselect.querySelector(".multiselect-options");

        // 點擊按鈕，展開或收合選單
        trigger.addEventListener("click", function () {
            const shouldOpen = options.hidden;

            // 先關閉其他教學複選選單
            teachingMultiselects.forEach(closeTeachingDropdown);

            // 再依照原本狀態決定是否展開
            options.hidden = !shouldOpen;
            trigger.setAttribute("aria-expanded", String(shouldOpen));
        });

        // 勾選或取消勾選時，更新按鈕文字
        options.addEventListener("change", function (event) {
            if (event.target.matches('input[type="checkbox"]')) {
                updateTeachingText(multiselect);
            }
        });

        // 老師既有資料載入後，重新更新複選選單文字
        multiselect.addEventListener("change", function (event) {

            // 避免與 checkbox 原本的 change 事件重複處理
            if (event.target === multiselect) {
                updateTeachingText(multiselect);
            }

        });

        // 初始化按鈕文字
        updateTeachingText(multiselect);
    });

    // 點擊選單外部時，自動收起
    document.addEventListener("click", function (event) {
        teachingMultiselects.forEach(function (multiselect) {
            if (!multiselect.contains(event.target)) {
                closeTeachingDropdown(multiselect);
            }
        });
    });

    // 按下 Esc，收起教學科目及年級選單
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            teachingMultiselects.forEach(function (multiselect) {
                closeTeachingDropdown(multiselect);
            });
        }
    });

});

// ==============================
// Experience 教學年資單位位置
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    const experienceInput = document.getElementById("teacher-experience");
    const experienceUnit = document.querySelector(".teacher-experience-unit");

    // 根據輸入數字長度，調整「年」的位置
    function updateExperienceUnitPosition() {
        const value = experienceInput.value || experienceInput.placeholder;
        const offset = value.length * 11;

        experienceUnit.style.left = `${22 + offset}px`;
    }

    // 輸入數字時更新位置
    experienceInput.addEventListener("input", updateExperienceUnitPosition);

    // 頁面載入時先更新一次
    updateExperienceUnitPosition();

    const teacherForm = document.getElementById("teacher-application-form");

    teacherForm.addEventListener("reset", function () {
        requestAnimationFrame(updateExperienceUnitPosition);
    });

});

// ==============================
// Availability 每週可授課時段
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    // 取得行程表、清除按鈕及已選時段數量
    const availabilityGrid = document.getElementById("teacher-availability");
    const clearButton = document.getElementById("teacher-availability-clear");
    const countText = document.getElementById("teacher-availability-count");

    // 取得所有可授課時段的 checkbox
    const availabilityCheckboxes = availabilityGrid.querySelectorAll(
        'input[type="checkbox"][name="availability"]'
    );

    // 更新已選擇的時段數量
    function updateAvailabilityCount() {

        // 計算目前有幾個時段被勾選
        const selectedCount = Array.from(availabilityCheckboxes).filter(
            function (checkbox) {
                return checkbox.checked;
            }
        ).length;

        // 更新畫面文字
        countText.textContent = `已選擇 ${selectedCount} 個時段`;
    }

    // 勾選、取消勾選或載入既有資料時，更新數量
    availabilityGrid.addEventListener("change", function (event) {

        if (
            event.target === availabilityGrid ||
            event.target.matches('input[type="checkbox"]')
        ) {
            updateAvailabilityCount();
        }

    });

    // 點擊「清除全部」，取消所有時段
    clearButton.addEventListener("click", function () {

        availabilityCheckboxes.forEach(function (checkbox) {
            checkbox.checked = false;
        });

        // 更新數量
        updateAvailabilityCount();

    });

    // 初始化已選時段數量
    updateAvailabilityCount();

    // 表單重設後，同步更新授課時段數量
    const teacherForm = document.getElementById("teacher-application-form");

    teacherForm.addEventListener("reset", function () {

        requestAnimationFrame(updateAvailabilityCount);

    });

});

// ==============================
// Validation 老師申請表單驗證
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("teacher-application-form");

    // 會員登出時，清除老師申請表單
    window.addEventListener("tutorlink:logout", function () {

        // 清除一般表單欄位與 checkbox
        form.reset();

        // 清除所有錯誤提示（包含頭貼區域）
        document.querySelectorAll(".teacher-error-message").forEach(function (error) {
            error.remove();
        });

        form.querySelectorAll(".teacher-field-error").forEach(function (field) {
            field.classList.remove("teacher-field-error");
        });

    });

    // 取得一般輸入欄位
    const nameInput = document.getElementById("teacher-name");
    const genderInput = document.getElementById("teacher-gender");
    const educationInput = document.getElementById("teacher-education");
    const hourlyRateInput = document.getElementById("teacher-hourly-rate");
    const experienceInput = document.getElementById("teacher-experience");
    const introductionInput = document.getElementById("teacher-introduction");
    const photoInput = document.getElementById("teacher-photo");
    const photoSection = document.querySelector(".teacher-photo-section");

    // 取得自訂複選欄位
    const locationContainer = document.getElementById(
        "teacher-selected-locations"
    );

    const subjectInputs = document.querySelectorAll(
        '#teacher-subjects input[type="checkbox"]'
    );

    const gradeInputs = document.querySelectorAll(
        '#teacher-grades input[type="checkbox"]'
    );

    const availabilityInputs = document.querySelectorAll(
        '#teacher-availability input[type="checkbox"]'
    );

    // 檢查是否至少勾選一個選項
    function hasCheckedInput(inputs) {
        return Array.from(inputs).some(function (input) {
            return input.checked;
        });
    }

    // 顯示欄位下方的錯誤提示
    function showError(message, element) {

        // 清除上一次的錯誤提示
        form.querySelectorAll(".teacher-error-message").forEach(function (error) {
            error.remove();
        });

        form.querySelectorAll(".teacher-field-error").forEach(function (field) {
            field.classList.remove("teacher-field-error");
        });

        // 找到欄位所屬的外層容器
        const field = element.closest(".teacher-field");

        if (!field) {
            return;
        }

        // 標記驗證失敗的欄位
        field.classList.add("teacher-field-error");

        // 建立錯誤訊息
        const errorMessage = document.createElement("p");
        errorMessage.className = "teacher-error-message";
        errorMessage.textContent = message;
        errorMessage.setAttribute("role", "alert");

        // 將錯誤提示放在欄位最下方
        field.appendChild(errorMessage);

        // 捲動到錯誤欄位
        field.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

        // 將焦點移到對應輸入欄位
        element.focus({ preventScroll: true });
    }

    // 清除指定欄位的錯誤提示
    function clearFieldError(element) {

        const field = element.closest(".teacher-field");

        if (!field) {
            return;
        }

        field.classList.remove("teacher-field-error");

        const errorMessage = field.querySelector(".teacher-error-message");

        if (errorMessage) {
            errorMessage.remove();
        }
    }

    // 一般輸入欄位：輸入或選擇後，清除錯誤提示
    [
        nameInput,
        genderInput,
        educationInput,
        hourlyRateInput,
        experienceInput,
        introductionInput
    ].forEach(function (input) {

        input.addEventListener("input", function () {
            clearFieldError(input);
        });

        input.addEventListener("change", function () {
            clearFieldError(input);
        });
    });

    // 教學地區：新增地區後，清除錯誤提示
    const locationObserver = new MutationObserver(function () {

        // 至少選擇一個教學地區
        if (locationContainer.children.length > 0) {

            // 從縣市選單找到教學地區欄位
            const citySelect = document.getElementById("teacher-city");

            // 清除教學地區的紅色提示
            clearFieldError(citySelect);
        }
    });

    // 監聽已選地區標籤的新增與移除
    locationObserver.observe(locationContainer, {
        childList: true
    });


    // 教學科目與年級：勾選後清除錯誤提示
    [subjectInputs, gradeInputs].forEach(function (inputs) {

        inputs.forEach(function (checkbox) {

            checkbox.addEventListener("change", function () {

                if (hasCheckedInput(inputs)) {
                    clearFieldError(checkbox);
                }
            });
        });
    });

    // 每週可授課時段：勾選後清除錯誤提示
    availabilityInputs.forEach(function (checkbox) {

        checkbox.addEventListener("change", function () {

            if (hasCheckedInput(availabilityInputs)) {
                clearFieldError(checkbox);
            }
        });
    });


    // 按照表單畫面順序進行驗證
    form.addEventListener("submit", async function (event) {

        // 目前尚未串接後端
        event.preventDefault();

        // 0. 個人頭貼
        // 新增老師時維持原本的必填規則
        // 編輯老師資料時，不需要重新選擇照片
        if (currentTeacherProfile === null && photoInput.files.length === 0) {

            // 避免重複產生錯誤訊息
            let errorMessage = photoSection.querySelector(
                ".teacher-error-message"
            );

            if (!errorMessage) {
                errorMessage = document.createElement("p");
                errorMessage.className = "teacher-error-message";
                errorMessage.setAttribute("role", "alert");
                photoSection.appendChild(errorMessage);
            }

            errorMessage.textContent = "請上傳個人照片";

            photoSection.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });

            return;
        }

        // 已上傳照片，清除錯誤提示
        const photoError = photoSection.querySelector(
            ".teacher-error-message"
        );

        if (photoError) {
            photoError.remove();
        }

        // 1. 姓名
        if (!nameInput.value.trim()) {
            showError("請輸入姓名", nameInput);
            return;
        }

        // 2. 性別
        if (!genderInput.value) {
            showError("請選擇性別", genderInput);
            return;
        }

        // 3. 教學地區
        if (locationContainer.children.length === 0) {
            showError(
                "請至少選擇一個教學地區",
                document.getElementById("teacher-city")
            );
            return;
        }

        // 4. 最高學歷
        if (!educationInput.value.trim()) {
            showError("請輸入最高學歷", educationInput);
            return;
        }

        // 5. 教學年級
        if (!hasCheckedInput(gradeInputs)) {
            showError(
                "請至少選擇一個教學年級",
                document.querySelector(
                    "#teacher-grades .multiselect-trigger"
                )
            );
            return;
        }

        // 6. 每小時收費
        if (!hourlyRateInput.value) {
            showError("請輸入每小時收費", hourlyRateInput);
            return;
        }

        // 檢查收費是否符合 HTML 的 min、step 等規則
        if (!hourlyRateInput.checkValidity()) {
            showError(
                "每小時收費請輸入有效的 50 元級距",
                hourlyRateInput
            );
            return;
        }

        // 7. 教學科目
        if (!hasCheckedInput(subjectInputs)) {
            showError(
                "請至少選擇一個教學科目",
                document.querySelector(
                    "#teacher-subjects .multiselect-trigger"
                )
            );
            return;
        }

        // 8. 教學年資
        if (experienceInput.value === "") {
            showError("請輸入教學年資", experienceInput);
            return;
        }

        // 檢查年資必須為 0 以上，且以 0.5 年為級距
        const experience = Number(experienceInput.value);

        if (
            !Number.isFinite(experience) ||
            experience < 0 ||
            !Number.isInteger(experience * 2)
        ) {
            showError("教學年資請以 0.5 年為級距，例如 0.5、1、1.5", experienceInput);
            return;
        }

        // 9. 每週可授課時段
        if (!hasCheckedInput(availabilityInputs)) {
            showError(
                "請至少選擇一個可授課時段",
                document.querySelector(
                    '#teacher-availability input[type="checkbox"]'
                )
            );
            return;
        }

        // 10. 自我介紹
        if (!introductionInput.value.trim()) {
            showError("請填寫教學經驗與個人介紹", introductionInput);
            return;
        }

        // 驗證通過後，清除舊的錯誤提示
        form.querySelectorAll(".teacher-error-message").forEach(function (error) {
            error.remove();
        });

        form.querySelectorAll(".teacher-field-error").forEach(function (field) {
            field.classList.remove("teacher-field-error");
        });

        // ==============================
        // 所有欄位驗證通過，整理老師申請資料
        // ==============================

        // 1. 取得教學地區
        const selectedLocations = window.getTeacherSelectedLocations();

        // 將前端縣市代碼轉換成中文名稱
        const citySelect = document.getElementById("teacher-city");

        const locations = selectedLocations.map(function (location) {

            const cityOption = Array.from(citySelect.options).find(
                function (option) {
                    return option.value === location.city;
                }
            );

            return {
                city: cityOption
                    ? cityOption.textContent.trim()
                    : location.city,
                district: location.district
            };
        });

        // 2. 取得已選擇的教學年級
        const grades = Array.from(gradeInputs)
            .filter(function (checkbox) {
                return checkbox.checked;
            })
            .map(function (checkbox) {
                return checkbox.value;
            });

        // 3. 取得已選擇的教學科目
        const subjects = Array.from(subjectInputs)
            .filter(function (checkbox) {
                return checkbox.checked;
            })
            .map(function (checkbox) {
                return checkbox.value;
            });

        // 4. 取得每週可授課時段
        const availability = Array.from(availabilityInputs)
            .filter(function (checkbox) {
                return checkbox.checked;
            })
            .map(function (checkbox) {

                // 例如 "1-evening" → day: 1, period: "evening"
                const [day, period] = checkbox.value.split("-");

                return {
                    day: Number(day) === 0 ? 7 : Number(day),
                    period: period
                };
            });

        // 5. 整理完整的老師申請資料
        const teacherData = {
            name: nameInput.value.trim(),
            gender: genderInput.value,
            locations: locations,
            education: educationInput.value.trim(),
            grades: grades,
            hourly_rate: Number(hourlyRateInput.value),
            subjects: subjects,
            experience: experience,
            availability: availability,
            intro: introductionInput.value.trim()
        };

        // 6. 頭貼先保留 File 物件
        const photoFile = photoInput.files[0];

        // 7. 取得目前登入會員的 JWT Token
        const token = sessionStorage.getItem("tutorlink_token");

        // 尚未登入時，不允許送出老師申請
        if (!token) {
            alert("請先登入會員，再申請成為家教老師");
            return;
        }

        // 8. 暫時在 Console 檢查資料
        console.log("老師申請資料：", teacherData);

        // 有選擇新照片時，才顯示檔案資訊
        if (photoFile) {
            console.log("頭貼檔案資訊：", {
                name: photoFile.name,
                type: photoFile.type,
                size: photoFile.size
            });
        }

        // 9. 判斷目前是新增老師，還是編輯既有老師資料
        const isEditMode = currentTeacherProfile !== null;

        const apiUrl = isEditMode
            ? "/api/teachers/me"
            : "/api/teachers";

        const apiMethod = isEditMode ? "PUT" : "POST";

        // 將老師資料送到後端
        try {
            const response = await fetch(apiUrl, {
                method: apiMethod,
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(teacherData)
            });

            const result = await response.json();

            // 新增成功：HTTP 201
            // 更新成功：HTTP 200
            if (
                (!isEditMode && response.status === 201) ||
                (isEditMode && response.status === 200)
            ) {

                console.log("老師 ID：", result.teacher_id);

                // 上傳老師頭貼至 AWS S3
                // 只有選擇新照片時才進行上傳
                if (photoFile) {

                    // 使用 FormData 傳送圖片檔案
                    const photoFormData = new FormData();
                    photoFormData.append("photo", photoFile);

                    let photoResponse;

                    try {
                        photoResponse = await fetch("/api/teachers/me/photo", {
                            method: "POST",
                            headers: {
                                "Authorization": `Bearer ${token}`
                            },
                            body: photoFormData
                        });

                    } catch (error) {
                        console.error("頭貼上傳連線失敗：", error);
                        alert("老師資料已儲存，但頭貼上傳失敗，請重新上傳照片");
                        await loadMyTeacherProfile();
                        return;
                    }

                    // 確認照片上傳成功
                    if (!photoResponse.ok) {
                        console.error("頭貼上傳失敗：", photoResponse.status);
                        alert("老師資料已儲存，但頭貼上傳失敗，請重新上傳照片");
                        await loadMyTeacherProfile();
                        return;
                    }

                    const photoResult = await photoResponse.json();

                    console.log("頭貼上傳成功：", photoResult.photo_key);

                    // 清除已選擇的檔案
                    // 避免下次修改老師資料時重複上傳同一張照片
                    photoInput.value = "";
                }

                // 老師資料儲存成功後，重新取得最新資料
                // 暫時不要自動跳轉，讓成功通知視窗正常顯示
                await loadMyTeacherProfile(false);

                // 取得老師 ID
                const savedTeacherId = currentTeacherProfile?.id ?? result.teacher_id;

                // 確認老師 ID 存在，才進行頁面跳轉
                if (savedTeacherId) {

                // 取得成功通知視窗
                const successModal = document.getElementById(
                    "teacher-success-modal"
                );

                const successTitle = document.getElementById(
                    "teacher-success-title"
                );

                // 根據新增或編輯模式顯示不同文字
                successTitle.textContent = isEditMode
                    ? "老師資料更新成功！"
                    : "老師申請成功！";

                // 顯示成功通知
                successModal.hidden = false;

                // 1.5 秒後自動跳轉
                setTimeout(function () {
                    window.location.href =
                        `/teacher-detail.html?id=${savedTeacherId}`;
                }, 1500);

                return;
            }

                // 無法取得 ID 時，留在表單並顯示提示
                alert("老師資料已儲存，但無法取得老師 ID，請重新整理頁面");
                return;
            }

                // 尚未登入或登入已過期
                if (response.status === 401) {
                    alert("登入已過期，請重新登入");
                    return;
                }

                // 會員權限不足
                if (response.status === 403) {
                    alert("目前帳號沒有申請老師的權限");
                    return;
                }

                // 已經建立過老師資料
                if (response.status === 409) {
                    alert("你已經建立過老師資料，無法重複申請");
                    return;
                }

                // 其他錯誤
                console.error("老師申請失敗：", result);
                alert("老師申請失敗，請稍後再試");

            } catch (error) {
                console.error("連線錯誤：", error);
                alert("無法連線至伺服器，請稍後再試");
            }

        });

        // 選擇照片後，自動清除頭貼錯誤提示
        photoInput.addEventListener("change", function () {

            if (photoInput.files.length > 0) {
                const errorMessage = photoSection.querySelector(
                    ".teacher-error-message"
                );

                if (errorMessage) {
                    errorMessage.remove();
                }
            }
        });

    });

// ==============================
// 頁面載入後，查詢老師既有資料
// ==============================
document.addEventListener("DOMContentLoaded", async function () {

    // 先確認會員是否已登入
    const isLoggedIn = await checkTeacherPageLogin();

    // 尚未登入，不查詢老師資料
    if (!isLoggedIn) {
        return;
    }

    // 已登入，查詢老師既有資料
    await loadMyTeacherProfile();

});

// ==============================
// 會員登入成功後，自動載入老師資料
// ==============================
window.addEventListener("tutorlink:login", async function () {
    const isLoggedIn = await checkTeacherPageLogin();

    if (isLoggedIn) {
        await loadMyTeacherProfile();
    }
});
