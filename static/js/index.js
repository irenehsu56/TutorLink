if (window.lucide) {lucide.createIcons();}

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

// 讀取縣市對應的行政區 JSON
fetch("/static/data/districts.json")
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
    });

// 點擊地區選單外面時，自動收起
document.addEventListener("click", function (event) {
    if (!locationField.contains(event.target)) {
        locationDropdown.hidden = true;
        locationTrigger.setAttribute("aria-expanded", "false");
    }
});

// ==============================
// Search 首頁搜尋跳轉功能
// ==============================

// 取得搜尋表單、科目與年級選單
const searchForm = document.getElementById("search");
const subjectSelect = document.getElementById("subject");
const gradeSelect = document.getElementById("grade");

// 使用者點擊「搜尋家教老師」時執行
searchForm.addEventListener("submit", function (event) {
    // 阻止表單預設送出
    event.preventDefault();

    // 建立網址搜尋參數
    const params = new URLSearchParams();

    // 取得四個搜尋條件
    const subject = subjectSelect.value;
    const city = locationSelect.value;
    const district = districtSelect.value;
    const grade = gradeSelect.value;

    // 只加入有選擇的條件
    if (subject) {
        params.set("subject", subject);
    }

    if (city) {
        params.set("city", city);

        if (district) {
            params.set("district", district);
        }
    }

    if (grade) {
        params.set("grade", grade);
    }

    // 跳轉到老師列表頁，並帶入搜尋條件
    const queryString = params.toString();

    window.location.href = queryString
        ? `/teachers.html?${queryString}`
        : "/teachers.html";
});
