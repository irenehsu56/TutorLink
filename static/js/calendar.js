if (window.lucide) {lucide.createIcons();}

// ==============================
// Calendar 個人行事曆
// ==============================
document.addEventListener("DOMContentLoaded", () => {

    // 我的課程｜分頁切換
    const calendarTab = document.getElementById("calendar-tab-calendar");
    const recordsTab = document.getElementById("calendar-tab-records");

    const calendarPanel = document.getElementById("calendar-panel-calendar");
    const recordsPanel = document.getElementById("calendar-panel-records");

    // 切換目前顯示的分頁
    function switchCourseTab(tabName) {
        const showCalendar = tabName === "calendar";

        // 更新分頁按鈕狀態
        calendarTab.classList.toggle("active", showCalendar);
        recordsTab.classList.toggle("active", !showCalendar);

        calendarTab.setAttribute("aria-selected", String(showCalendar));
        recordsTab.setAttribute("aria-selected", String(!showCalendar));

        // 更新分頁內容
        calendarPanel.hidden = !showCalendar;
        recordsPanel.hidden = showCalendar;
    }

    // 點擊行事曆
    calendarTab.addEventListener("click", () => {
        switchCourseTab("calendar");
    });

    // 點擊課程紀錄
    recordsTab.addEventListener("click", () => {
        switchCourseTab("records");
    });

    // 取得目前日期
    const today = new Date();

    // 目前顯示的年份、月份
    let displayedYear = today.getFullYear();
    let displayedMonth = today.getMonth();

    // 課程紀錄獨立顯示的年份、月份
    let recordsYear = today.getFullYear();
    let recordsMonth = today.getMonth();

    // 課程紀錄分類：null 代表顯示全部
    let activeRecordFilter = null;

    // 儲存目前登入會員的所有預約
    let myBookings = [];

    // 儲存目前登入會員的 ID
    let currentUserId = null;

    // 個人行事曆｜預約狀態篩選
    // null：顯示全部狀態、confirmed：只顯示已確認、pending：只顯示待確認、cancelled：只顯示已取消／已拒絕
    let activeStatusFilter = null;

    // HTML 元素
    const monthTitle = document.getElementById("calendar-month-title");
    const calendarDays = document.getElementById("calendar-days");
    const prevMonthBtn = document.getElementById("calendar-prev-month");
    const nextMonthBtn = document.getElementById("calendar-next-month");

    // 更新當月預約統計
    function updateBookingStats() {

        // 篩選目前顯示月份的預約
        const monthlyBookings = myBookings.filter(booking => {

            const [year, month] = booking.booking_date
                .split("-")
                .map(Number);

            return (
                year === displayedYear &&
                month === displayedMonth + 1
            );
        });

        // 計算各狀態的預約數量
        const acceptedCount = monthlyBookings.filter(
            booking => booking.status === "accepted"
        ).length;

        const pendingCount = monthlyBookings.filter(
            booking => booking.status === "pending"
        ).length;

        const cancelledCount = monthlyBookings.filter(
            booking => ["cancelled", "rejected"].includes(booking.status)
        ).length;

        // 更新上方三張統計卡片的數字
        document.getElementById("calendar-confirmed-count").textContent =
            acceptedCount;

        document.getElementById("calendar-pending-count").textContent =
            pendingCount;

        document.getElementById("calendar-cancelled-count").textContent =
            cancelledCount;
    }

    // 取得目前登入會員的預約資料
    async function loadMyBookings() {

        // 取得登入會員的 JWT
        const token = sessionStorage.getItem("tutorlink_token");

        if (!token) {
            myBookings = [];
            renderCalendar();
            resetDayBookings();
            updateBookingStats();
            renderCourseRecords();
            return;
        }

        try {
            // 呼叫目前會員的預約清單 API
            const response = await fetch("/api/bookings/me", {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error("取得預約資料失敗");
            }

            const data = await response.json();

            // 避免登入身分已改變時使用舊資料
            if (sessionStorage.getItem("tutorlink_token") !== token) {
                return;
            }

            // 暫時輸出資料，確認 API 正常運作
            console.log("個人行事曆預約資料：", data.bookings);

            myBookings = Array.isArray(data.bookings) ? data.bookings : [];

            // 重新渲染月曆，顯示預約狀態圓點
            renderCalendar();

            // 更新當月預約統計
            updateBookingStats();

            // 更新課程紀錄清單
            renderCourseRecords();

        } catch (error) {
            console.error("載入個人行事曆預約失敗：", error);
        }
    }

    // 課程完成確認視窗
    const completeLessonModal = document.getElementById("complete-lesson-modal");
    const completeLessonCancel = document.getElementById("complete-lesson-cancel");
    const completeLessonSubmit = document.getElementById("complete-lesson-submit");

    let completeLessonResolver = null;
    let completeLessonPreviousFocus = null;

    function closeCompleteLessonModal(confirmed) {
        if (completeLessonModal.hidden) return;

        completeLessonModal.hidden = true;

        const resolve = completeLessonResolver;
        completeLessonResolver = null;

        if (completeLessonPreviousFocus?.isConnected) {
            completeLessonPreviousFocus.focus();
        }
        completeLessonPreviousFocus = null;

        if (resolve) resolve(confirmed);
    }

    function confirmLessonCompletion() {
        // 防止重複開啟
        if (completeLessonResolver) return Promise.resolve(false);

        completeLessonPreviousFocus = document.activeElement;
        completeLessonModal.hidden = false;
        completeLessonSubmit.focus();

        return new Promise(resolve => {
            completeLessonResolver = resolve;
        });
    }

    completeLessonCancel.addEventListener("click", () => {
        closeCompleteLessonModal(false);
    });

    completeLessonSubmit.addEventListener("click", () => {
        closeCompleteLessonModal(true);
    });

    completeLessonModal.addEventListener("click", event => {
        if (event.target === completeLessonModal) {
            closeCompleteLessonModal(false);
        }
    });

    completeLessonModal.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            event.preventDefault();
            closeCompleteLessonModal(false);
        }

        // 焦點維持在視窗內
        if (event.key === "Tab") {
            const buttons = [completeLessonCancel, completeLessonSubmit];
            const index = buttons.indexOf(document.activeElement);

            if (event.shiftKey && index === 0) {
                event.preventDefault();
                completeLessonSubmit.focus();
            } else if (!event.shiftKey && index === 1) {
                event.preventDefault();
                completeLessonCancel.focus();
            }
        }
    });

    // 課程紀錄｜學生課後評價視窗
    const courseReviewModal = document.getElementById("course-review-modal");
    const courseReviewContent = document.getElementById("course-review-content");
    const courseReviewCount = document.getElementById("course-review-count");
    const courseReviewError = document.getElementById("course-review-error");
    const courseReviewCancel = document.getElementById("course-review-cancel");
    const courseReviewSubmit = document.getElementById("course-review-submit");

    let reviewingBookingId = null;
    let reviewPreviousFocus = null;

    function closeCourseReviewModal() {
        if (!courseReviewModal || courseReviewModal.hidden) return;

        courseReviewModal.hidden = true;
        reviewingBookingId = null;

        if (reviewPreviousFocus?.isConnected) {
            reviewPreviousFocus.focus();
        }

        reviewPreviousFocus = null;
    }

    function openCourseReviewModal(booking) {
        if (!courseReviewModal || !booking) return;

        reviewingBookingId = booking.id;
        reviewPreviousFocus = document.activeElement;

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

        document.getElementById("course-review-subject").textContent =
            `${subjectLabels[booking.subject] || booking.subject || "未提供"}家教課程`;

        document.getElementById("course-review-teacher").textContent =
            `老師：${booking.teacher_name || "未提供"}`;

        document.getElementById("course-review-date").textContent =
            `上課日期：${booking.booking_date || "未提供"}`;

        courseReviewContent.value = "";
        courseReviewCount.textContent = "0 / 200";
        courseReviewError.textContent = "";
        courseReviewError.hidden = true;

        courseReviewModal.hidden = false;
        courseReviewContent.focus();
    }

    // 即時字數計算
    courseReviewContent.addEventListener("input", () => {
        courseReviewCount.textContent =
            `${courseReviewContent.value.length} / 200`;

        courseReviewError.hidden = true;
    });

    // 取消
    courseReviewCancel.addEventListener("click", closeCourseReviewModal);

    // 點擊視窗外側關閉
    courseReviewModal.addEventListener("click", event => {
        if (event.target === courseReviewModal) {
            closeCourseReviewModal();
        }
    });

    // Escape 關閉、Tab 焦點限制
    courseReviewModal.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            event.preventDefault();
            closeCourseReviewModal();
            return;
        }

        if (event.key !== "Tab") return;

        const focusable = [
            courseReviewContent,
            courseReviewCancel,
            courseReviewSubmit
        ];

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });

    // 學生送出課後評價
    courseReviewSubmit.addEventListener("click", async () => {
        const content = courseReviewContent.value.trim();

        if (content.length > 200) {
            courseReviewError.textContent = "評價內容不能超過 200 字";
            courseReviewError.hidden = false;
            courseReviewContent.focus();
            return;
        }

        courseReviewError.hidden = true;

        if (!content) {
            courseReviewError.textContent = "請先填寫課後評價";
            courseReviewError.hidden = false;
            courseReviewContent.focus();
            return;
        }

        if (content.length > 200) {
            courseReviewError.textContent = "評價內容不能超過 200 字";
            courseReviewError.hidden = false;
            return;
        }

        if (!reviewingBookingId) {
            courseReviewError.textContent = "找不到課程資料";
            courseReviewError.hidden = false;
            return;
        }

        const token = sessionStorage.getItem("tutorlink_token");

        if (!token) {
            courseReviewError.textContent = "請先登入會員";
            courseReviewError.hidden = false;
            return;
        }

        courseReviewSubmit.disabled = true;
        courseReviewSubmit.textContent = "送出中...";

        try {
            const response = await fetch("/api/reviews", {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    booking_id: reviewingBookingId,
                    content: content
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "評價送出失敗，請稍後再試"
                );
            }

            if (sessionStorage.getItem("tutorlink_token") !== token) {
                closeCourseReviewModal();
                return;
            }

            closeCourseReviewModal();

            showCalendarToast("課後評價發表成功！", "success");

        } catch (error) {
            courseReviewError.textContent = error.message;
            courseReviewError.hidden = false;

        } finally {
            courseReviewSubmit.disabled = false;
            courseReviewSubmit.textContent = "送出評價";
        }
    });
    // TutorLink｜課程頁面共用 Toast 通知
    let calendarToastTimer = null;

    function showCalendarToast(message, type = "info") {
        let toast = document.getElementById("calendar-toast");

        if (!toast) {
            toast = document.createElement("div");
            toast.id = "calendar-toast";
            toast.className = "calendar-toast";
            toast.setAttribute("role", "status");
            toast.setAttribute("aria-live", "polite");
            document.body.appendChild(toast);
        }

        // 清除上一次的計時器
        if (calendarToastTimer) {
            clearTimeout(calendarToastTimer);
        }

        const icons = {
            success: "check-circle-2",
            error: "circle-alert",
            info: "info"
        };

        toast.className = `calendar-toast ${type}`;
        toast.replaceChildren();

        const icon = document.createElement("i");
        icon.setAttribute("data-lucide", icons[type] || icons.info);

        const text = document.createElement("span");
        text.textContent = message;

        toast.append(icon, text);

        if (window.lucide) {
            lucide.createIcons({ nodes: [toast] });
        }

        // 顯示通知
        requestAnimationFrame(() => {
            toast.classList.add("show");
        });

        // 3 秒後自動消失
        calendarToastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, 3000);
    }

    // 我的課程｜課程紀錄清單
    function renderCourseRecords() {
        const recordsList = document.getElementById("calendar-records-list");
        const recordsMonthTitle = document.getElementById("records-month-title");

        if (!recordsList || !recordsMonthTitle) return;

        // 更新課程紀錄月份標題
        recordsMonthTitle.textContent =
            `${recordsYear} 年 ${recordsMonth + 1} 月`;

        recordsList.replaceChildren();

        // 取得當月份已接受的預約
        const monthlyRecords = myBookings
            .filter(booking => {
                if (booking.status !== "accepted") return false;

                const [year, month] = booking.booking_date
                    .split("-")
                    .map(Number);

                return (
                    year === recordsYear &&
                    month === recordsMonth + 1
                );
            })
            .sort((a, b) => {
                const dateA = `${a.booking_date}T${a.start_time}`;
                const dateB = `${b.booking_date}T${b.start_time}`;

                // 由舊到新：日期越早、時間越早，排在越前面
                return dateA.localeCompare(dateB);
            });

        // 統一時間格式
        function formatCourseTime(time) {
            const match = String(time ?? "")
                .trim()
                .match(/^(\d{1,2}):(\d{1,2})(?::(\d{0,2}))?$/);

            if (!match) return "--:--";

            const hour = Number(match[1]);
            const minute = Number(match[2]);

            if (hour > 23 || minute > 59) return "--:--";

            return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
        }

        // 判斷課程是否已過結束時間
        function hasLessonEnded(booking) {
            const date = String(booking.booking_date || "").slice(0, 10);
            const time = formatCourseTime(booking.end_time);

            if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || time === "--:--") {
                return false;
            }

            const [year, month, day] = date.split("-").map(Number);
            const [hour, minute] = time.split(":").map(Number);

            const endDateTime = new Date(
                year,
                month - 1,
                day,
                hour,
                minute
            );

            return (
                endDateTime.getFullYear() === year &&
                endDateTime.getMonth() === month - 1 &&
                endDateTime.getDate() === day &&
                endDateTime <= new Date()
            );
        }

        // 待確認完成：已上完課，但老師尚未確認
        const pendingRecords = monthlyRecords.filter(booking => {
            return hasLessonEnded(booking) && !booking.completed_at;
        });

        // 付款紀錄：所有已接受預約的課程，且尚未付款成功
        // 不論課程是否已經上完，都要列入
        const paymentRecords = monthlyRecords.filter(booking => {
            return (
                booking.status === "accepted" &&
                booking.payment_status !== "paid"
            );
        });

        // 已完成：課程已完成，而且付款成功
        const completedRecords = monthlyRecords.filter(booking => {
            return (
                Boolean(booking.completed_at) &&
                booking.payment_status === "paid"
            );
        });

        // 更新分類數量
        document.getElementById("records-pending-count").textContent =
            pendingRecords.length;

        document.getElementById("records-payments-count").textContent =
            paymentRecords.length;

        document.getElementById("records-completed-count").textContent =
            completedRecords.length;

        // 依目前選取的分類決定顯示內容
        let records = monthlyRecords;

        if (activeRecordFilter === "pending") {
            records = pendingRecords;
        } else if (activeRecordFilter === "payments") {
            records = paymentRecords;
        } else if (activeRecordFilter === "completed") {
            records = completedRecords;
        }

        // 沒有課程紀錄
        if (records.length === 0) {
            const empty = document.createElement("p");
            empty.className = "calendar-records-empty";
            const emptyMessages = {
                pending: "本月沒有待確認完成的課程",
                payments: "本月沒有付款相關課程",
                completed: "目前尚無可確認付款成功的已完成課程"
            };

            empty.textContent =
                emptyMessages[activeRecordFilter] || "本月尚無課程紀錄";
            recordsList.appendChild(empty);
            return;
        }

        // 科目中文名稱
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

        records.forEach(booking => {
            const isTeacher =
                currentUserId !== null &&
                Number(booking.student_id) !== Number(currentUserId);

            const personName = isTeacher
                ? booking.student_name
                : booking.teacher_name;

            const personLabel = isTeacher ? "學生" : "老師";

            const isCompleted = Boolean(booking.completed_at);
            const lessonEnded = hasLessonEnded(booking);

            // 建立課程卡片
            const card = document.createElement("article");
            card.className = "calendar-record-card";

            // 課程名稱
            const title = document.createElement("h3");
            title.className = "calendar-record-title";
            title.textContent =
                `${subjectLabels[booking.subject] || booking.subject || "未提供"}家教課程`;

            // 判斷課程狀態
            let lessonStatusText = "";
            let lessonStatusClass = "";

            if (isCompleted) {
                lessonStatusText = "已上課";
                lessonStatusClass = "completed";
            } else if (lessonEnded) {
                lessonStatusText = "待確認完成";
                lessonStatusClass = "pending-completion";
            } else {
                lessonStatusText = "待上課";
                lessonStatusClass = "upcoming";
            }

            // 建立狀態標籤
            const status = document.createElement("span");
            status.className =
                `calendar-record-status ${lessonStatusClass}`;
            status.textContent = lessonStatusText;

            // 取得這堂課的實際付款狀態
            const paymentStatusValue = booking.payment_status || "unpaid";

            // 建立付款狀態標籤
            const paymentStatusBadge = document.createElement("span");
            paymentStatusBadge.className = "calendar-record-payment-status";


            if (paymentStatusValue === "paid") {
                // 正常付款成功
                paymentStatusBadge.classList.add("paid");
                paymentStatusBadge.textContent = isTeacher ? "已收款" : "已付款";

            } else if (paymentStatusValue === "refund_required") {
                // 異常付款：需要人工核對或退款
                paymentStatusBadge.classList.add("pending");
                paymentStatusBadge.textContent = "付款異常";

            } else {
                // 尚未付款成功
                paymentStatusBadge.classList.add("pending");
                paymentStatusBadge.textContent = isTeacher ? "待收款" : "待付款";
            }

            // 將上課狀態與付款狀態放在同一區
            const statusGroup = document.createElement("div");
            statusGroup.className = "calendar-record-status-group";

            statusGroup.append(status, paymentStatusBadge);

            // 卡片標題區
            const header = document.createElement("div");
            header.className = "calendar-record-header";
            header.append(title, statusGroup);

            const info = document.createElement("div");
            info.className = "calendar-record-info";

            const fields = [
                `${personLabel}：${personName || "未提供"}`,
                `上課日期：${booking.booking_date || "未提供"}`,
                `上課時間：${formatCourseTime(booking.start_time)}－${formatCourseTime(booking.end_time)}`,
                `課程長度：${booking.duration_minutes} 分鐘`,
                `課程金額：NT$ ${Number(booking.total_amount || 0).toLocaleString("en-US")}`
            ];

            fields.forEach(value => {
                const row = document.createElement("p");
                row.textContent = value;
                info.appendChild(row);
            });

            card.append(header, info);

            // 課程卡片共用操作按鈕區域
            const recordActions = document.createElement("div");
            recordActions.className = "calendar-record-actions";

            // 學生專屬｜立即付款按鈕
            // 判斷目前登入會員是否為這堂課的學生
            const isStudent =
                currentUserId !== null &&
                Number(booking.student_id) === Number(currentUserId);

            // 學生專屬：依照實際付款狀態顯示按鈕
            const paymentStatus = paymentStatusValue;

            // 只有學生本人、老師已接受預約，
            // 且沒有正常付款成功或異常付款紀錄時，才顯示付款按鈕
            const canShowPayment =
                isStudent &&
                booking.status === "accepted" &&
                paymentStatus !== "paid" &&
                paymentStatus !== "refund_required";

            if (canShowPayment) {
                const payButton = document.createElement("button");

                payButton.type = "button";
                payButton.className = "calendar-record-pay-button";

                payButton.textContent = "立即付款";

                recordActions.appendChild(payButton);

                // 只有尚未付款成功，才綁定付款事件
                if (paymentStatus !== "paid") {

                    // 學生專屬｜綠界付款
                    payButton.addEventListener("click", async () => {
                    const token = sessionStorage.getItem("tutorlink_token");

                    if (!token) {
                        showCalendarToast("請先登入會員", "error");
                        return;
                    }

                    // 防止重複點擊
                    payButton.disabled = true;
                    payButton.textContent = "正在前往付款頁面...";

                    try {
                        // 1. 呼叫後端建立付款訂單
                        const response = await fetch("/api/payments/create", {
                            method: "POST",
                            headers: {
                                "Authorization": `Bearer ${token}`,
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                booking_id: booking.id
                            })
                        });

                        let data = await response.json();

                        if (!response.ok) {
                            const detail = data.detail;

                            if (
                                response.status === 409 &&
                                ["PAYMENT_PENDING", "PAYMENT_RETRY_REQUIRED"].includes(detail?.code) &&
                                Number.isInteger(detail.payment_id) &&
                                detail.payment_id > 0
                            ) {
                                // 已有 pending 訂單，向後端確認能否繼續付款
                                const checkoutResponse = await fetch(
                                    `/api/payments/${detail.payment_id}/checkout`,
                                    {
                                        method: "GET",
                                        headers: {
                                            "Authorization": `Bearer ${token}`
                                        }
                                    }
                                );

                                data = await checkoutResponse.json();

                                if (!checkoutResponse.ok) {
                                    throw new Error(
                                        typeof data.detail === "string"
                                            ? data.detail
                                            : "目前無法繼續付款，請稍後再試"
                                    );
                                }

                            } else {
                                throw new Error(
                                    typeof detail === "string"
                                        ? detail
                                        : detail?.message || "建立付款訂單失敗"
                                );
                            }
                        }

                        // 避免登入身分在請求期間改變
                        if (sessionStorage.getItem("tutorlink_token") !== token) {
                            throw new Error("登入狀態已變更，請重新操作");
                        }

                        // 2. 檢查後端回傳的付款資料
                        if (!data.payment_url || !data.ecpay_params) {
                            throw new Error("付款資料不完整，請稍後再試");
                        }

                        const paymentUrl = new URL(data.payment_url);

                        // 限制只能跳轉到綠界 Sandbox
                        if (
                            paymentUrl.protocol !== "https:" ||
                            paymentUrl.hostname !== "payment-stage.ecpay.com.tw"
                        ) {
                            throw new Error("付款網址不正確，已取消跳轉");
                        }

                        // 3. 建立 POST 表單
                        const form = document.createElement("form");
                        form.method = "POST";
                        form.action = paymentUrl.href;
                        form.style.display = "none";

                        // 4. 將綠界付款參數加入表單
                        Object.entries(data.ecpay_params).forEach(([key, value]) => {
                            const input = document.createElement("input");

                            input.type = "hidden";
                            input.name = key;
                            input.value = String(value);

                            form.appendChild(input);
                        });

                        // 5. 加入頁面並送往綠界
                        document.body.appendChild(form);

                        showCalendarToast("正在前往綠界測試付款頁面...", "info");

                        form.submit();

                    } catch (error) {
                        console.error("建立綠界付款失敗：", error);

                        showCalendarToast(
                            error.message || "無法前往付款頁面，請稍後再試",
                            "error"
                        );

                        payButton.disabled = false;

                        payButton.textContent = "立即付款";
                    }
                });
            }
        }

            // 只有這筆課程的老師，且課程已結束、尚未確認完成，才顯示按鈕
            const canCompleteLesson =
                isTeacher &&
                booking.status === "accepted" &&
                hasLessonEnded(booking) &&
                !booking.completed_at;

            if (canCompleteLesson) {
                const actions = document.createElement("div");
                actions.className = "calendar-record-actions";

                const completeButton = document.createElement("button");
                completeButton.type = "button";
                completeButton.className = "calendar-record-complete-button";
                completeButton.textContent = "確認課程完成";

                actions.appendChild(completeButton);
                card.appendChild(actions);

                completeButton.addEventListener("click", async () => {
                    const confirmed = await confirmLessonCompletion();

                    if (!confirmed) return;

                    const token = sessionStorage.getItem("tutorlink_token");

                    if (!token) {
                        alert("請先登入會員");
                        return;
                    }

                    completeButton.disabled = true;
                    completeButton.textContent = "處理中...";

                    try {
                        const response = await fetch(
                            `/api/bookings/${booking.id}/complete`,
                            {
                                method: "PATCH",
                                headers: {
                                    "Authorization": `Bearer ${token}`
                                }
                            }
                        );

                        const data = await response.json();

                        if (!response.ok) {
                            throw new Error(
                                typeof data.detail === "string"
                                    ? data.detail
                                    : "確認課程完成失敗"
                            );
                        }

                        // 避免帳號已切換時重新載入舊帳號資料
                        if (sessionStorage.getItem("tutorlink_token") !== token) {
                            return;
                        }

                        // 重新取得預約資料，更新狀態及分類數量
                        await loadMyBookings();

                    } catch (error) {
                        console.error("確認課程完成失敗：", error);

                        alert(error.message || "操作失敗，請稍後再試");

                        completeButton.disabled = false;
                        completeButton.textContent = "確認課程完成";
                    }
                });
            }

            // 有操作按鈕時才加入卡片
            if (recordActions.children.length > 0) {
                card.appendChild(recordActions);
            }

            recordsList.appendChild(card);
        });
    }

    // 更新右側當日課程清單
    function renderDayBookings(year, month, day) {
        const selectedDate = document.getElementById("calendar-selected-date");
        const dayCount = document.getElementById("calendar-day-count");
        const bookingList = document.getElementById("calendar-booking-list");

        // 更新選取日期
        selectedDate.textContent = `${year} 年 ${month + 1} 月 ${day} 日`;

        // 組合日期字串（YYYY-MM-DD）
        const dateString =
            `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

        // 找出當天所有預約
        const dayBookings = myBookings.filter(
            booking => booking.booking_date === dateString
        );

        // 更新當天預約數量
        dayCount.textContent = `共 ${dayBookings.length} 筆課程預約`;

        // 暫時輸出當天預約資料
        console.log("當天預約資料：", dayBookings);

        // 當天沒有預約
        if (dayBookings.length === 0) {
            bookingList.innerHTML = `
                <div class="calendar-empty">
                    <i data-lucide="calendar-check"></i>
                    <p>當天沒有課程預約</p>
                </div>
            `;
        } else {
            // 清空原本的課程清單
            bookingList.replaceChildren();

            // 授課科目中英文對照
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

            // 預約狀態中文對照
            const statusLabels = {
                accepted: "已確認",
                pending: "待確認",
                cancelled: "已取消",
                rejected: "已拒絕"
            };

            // 依開始時間排序（轉換成分鐘比較）
            const timeToMinutes = (time) => {
                const [hour, minute] = String(time).split(":").map(Number);
                return hour * 60 + minute;
            };

            dayBookings.sort((a, b) =>
                timeToMinutes(a.start_time) - timeToMinutes(b.start_time)
            );

            // 產生每筆預約卡片
            dayBookings.forEach(booking => {

                // 判斷目前會員是否為這筆預約的老師
                const isTeacher =
                    currentUserId !== null &&
                    Number(booking.student_id) !== Number(currentUserId);

                // 根據這筆預約的身分，顯示對方姓名
                const personLabel = isTeacher ? "學生姓名" : "老師姓名";

                const personName = isTeacher
                    ? booking.student_name
                    : booking.teacher_name;

                // 只有老師可以處理尚未確認的預約
                const canManageBooking =
                    isTeacher && booking.status === "pending";

                // 學生可以取消自己待確認或已確認的預約
                const canCancelBooking =
                    currentUserId !== null &&
                    Number(booking.student_id) === Number(currentUserId) &&
                    ["pending", "accepted"].includes(booking.status);

                // 測試預約管理權限
                console.log("預約權限檢查：", {
                    bookingId: booking.id,
                    isTeacher: isTeacher,
                    canManageBooking: canManageBooking
                });

                const card = document.createElement("div");
                card.className = "calendar-booking-card";

                // 預約卡片支援鍵盤操作與展開／收合功能
                card.tabIndex = 0;
                card.setAttribute("role", "button");
                card.setAttribute("aria-label", "查看預約詳細資訊");

                const subject =
                    subjectLabels[booking.subject] ||
                    booking.subject ||
                    "未提供";

                const status =
                    statusLabels[booking.status] || "未知狀態";

                // 統一時間格式為 HH:MM
                const formatTime = (time) => {
                    const [hour, minute] = String(time).split(":");

                    return `${hour.padStart(2, "0")}:${minute}`;
                };

                const startTime = formatTime(booking.start_time);
                const endTime = formatTime(booking.end_time);

                const amount =
                    Number(booking.total_amount).toLocaleString("en-US");

                card.innerHTML = `
                    <div class="calendar-booking-header">
                        <strong>${subject}家教課程</strong>
                        <span class="calendar-booking-status ${booking.status}">
                            ${status}
                        </span>
                    </div>

                    <div class="calendar-booking-info">
                        <div>
                            <i data-lucide="user-round"></i>
                            <span class="calendar-booking-person"></span>
                        </div>

                        <div>
                            <i data-lucide="clock"></i>
                            <span>
                                ${startTime}－${endTime}
                                （${booking.duration_minutes} 分鐘）
                            </span>
                        </div>

                        <div>
                            <i data-lucide="wallet"></i>
                            <span>NT$ ${amount}</span>
                        </div>
                    </div>
                `;

                // 安全顯示學生／老師姓名，避免將姓名當成 HTML
                const personElement = card.querySelector(".calendar-booking-person");

                if (personElement) {
                    personElement.textContent =
                        `${personLabel}：${personName || "未提供"}`;
                }

                // 預約卡片｜展開詳細資訊
                // 每小時收費
                const hourlyRate =
                    Number(booking.hourly_rate).toLocaleString("en-US");

                // 預約狀態提示
                const noticeLabels = {
                    pending: "此預約正在等待老師確認。",
                    accepted: "此預約已確認，可前往聊天室聯絡對方。",
                    rejected: "此預約已被老師拒絕。",
                    cancelled: "此預約已取消。"
                };

                // 建立詳細資訊容器
                const details = document.createElement("div");
                details.className = "calendar-booking-details";
                details.id = `calendar-booking-details-${booking.id}`;
                details.hidden = true;

                details.innerHTML = `
                    <div class="calendar-booking-detail-title">
                        預約詳細資訊
                    </div>

                    <div class="calendar-booking-detail-row">
                        <span>上課日期</span>
                        <strong>${booking.booking_date.replaceAll("-", "/")}</strong>
                    </div>

                    <div class="calendar-booking-detail-row">
                        <span>上課時間</span>
                        <strong>${startTime}－${endTime}</strong>
                    </div>

                    <div class="calendar-booking-detail-row">
                        <span>課程長度</span>
                        <strong>${booking.duration_minutes} 分鐘</strong>
                    </div>

                    <div class="calendar-booking-detail-row">
                        <span>每小時收費</span>
                        <strong>NT$ ${hourlyRate}</strong>
                    </div>

                    <div class="calendar-booking-detail-row">
                        <span>課程總金額</span>
                        <strong>NT$ ${amount}</strong>
                    </div>

                    <div class="calendar-booking-detail-notice">
                        <i data-lucide="info"></i>
                        <span>${noticeLabels[booking.status] || "查看預約資訊與目前狀態。"}</span>
                    </div>

                    <button
                        type="button"
                        class="calendar-booking-chat-button">
                        前往聊天室
                    </button>

                    ${canManageBooking ? `
                        <div class="calendar-booking-actions">
                            <button
                                type="button"
                                class="calendar-booking-accept-button">
                                接受預約
                            </button>

                            <button
                                type="button"
                                class="calendar-booking-reject-button">
                                拒絕預約
                            </button>
                        </div>
                    ` : ""}

                    ${canCancelBooking ? `
                        <div class="calendar-booking-actions">
                            <button
                                type="button"
                                class="calendar-booking-cancel-button">
                                取消預約
                            </button>
                        </div>
                    ` : ""}
                `;

                card.appendChild(details);

                // 老師接受預約
                const acceptButton = details.querySelector(".calendar-booking-accept-button");

                if (acceptButton) {
                    acceptButton.addEventListener("click", async (event) => {
                        event.stopPropagation();

                        // 取得登入會員的 JWT
                        const token = sessionStorage.getItem("tutorlink_token");

                        if (!token) {
                            alert("請先登入會員");
                            return;
                        }

                        // 避免重複點擊
                        acceptButton.disabled = true;

                        try {
                            // 呼叫接受預約 API
                            const response = await fetch(`/api/bookings/${booking.id}/accept`, {
                                method: "PATCH",
                                headers: {
                                    "Authorization": `Bearer ${token}`
                                }
                            });

                            const data = await response.json();

                            if (!response.ok) {
                                throw new Error(data.detail || "接受預約失敗");
                            }

                            // 重新載入行事曆，更新預約狀態與統計
                            window.location.reload();

                        } catch (error) {
                            console.error("接受預約失敗：", error);

                            await showBookingErrorModal(
                                error.message || "接受預約失敗，請稍後再試"
                            );

                            // 失敗時恢復按鈕
                            acceptButton.disabled = false;
                        }
                    });
                }

                // 老師拒絕預約
                const rejectButton = details.querySelector(".calendar-booking-reject-button");

                if (rejectButton) {
                    rejectButton.addEventListener("click", async (event) => {
                        event.stopPropagation();

                        // 先確認是否拒絕
                        const confirmed = await showBookingRejectModal();
                        if (!confirmed) return;

                        const token = sessionStorage.getItem("tutorlink_token");

                        if (!token) {
                            await showBookingErrorModal("請先登入會員");
                            return;
                        }

                        rejectButton.disabled = true;

                        try {
                            const response = await fetch(`/api/bookings/${booking.id}/reject`, {
                                method: "PATCH",
                                headers: {
                                    "Authorization": `Bearer ${token}`
                                }
                            });

                            const data = await response.json();

                            if (!response.ok) {
                                throw new Error(
                                    typeof data.detail === "string"
                                        ? data.detail
                                        : "拒絕預約失敗"
                                );
                            }

                            // 拒絕成功後重新載入行事曆
                            window.location.reload();

                        } catch (error) {
                            console.error("拒絕預約失敗：", error);

                            await showBookingErrorModal(
                                error.message || "拒絕預約失敗，請稍後再試"
                            );

                        } finally {
                            rejectButton.disabled = false;
                        }
                    });
                }

                // 學生取消預約
                const cancelButton = details.querySelector(".calendar-booking-cancel-button");

                if (cancelButton) {
                    cancelButton.addEventListener("click", async (event) => {
                        event.stopPropagation();

                        // 顯示取消預約確認視窗
                        const confirmed = await showBookingCancelModal();

                        if (!confirmed) {
                            return;
                        }

                        // 取得登入會員的 JWT
                        const token = sessionStorage.getItem("tutorlink_token");

                        if (!token) {
                            await showBookingErrorModal("請先登入會員");
                            return;
                        }

                        // 避免重複點擊
                        cancelButton.disabled = true;

                        try {
                            // 呼叫學生取消預約 API
                            const response = await fetch(`/api/bookings/${booking.id}/cancel`, {
                                method: "PATCH",
                                headers: {
                                    "Authorization": `Bearer ${token}`
                                }
                            });

                            const data = await response.json();

                            if (!response.ok) {
                                throw new Error(
                                    typeof data.detail === "string"
                                        ? data.detail
                                        : "取消預約失敗"
                                );
                            }

                            // 取消成功後重新載入行事曆
                            window.location.reload();

                        } catch (error) {
                            console.error("取消預約失敗：", error);

                            await showBookingErrorModal(
                                error.message || "取消預約失敗，請稍後再試"
                            );

                        } finally {
                            cancelButton.disabled = false;
                        }
                    });
                }

                // 設定卡片與詳細資訊的關聯
                card.setAttribute("aria-expanded", "false");
                card.setAttribute("aria-controls", details.id);

                // 展開／收合卡片
                function toggleBookingDetails() {
                    const isExpanded = !details.hidden;

                    // 先收合其他預約卡片
                    bookingList.querySelectorAll(".calendar-booking-card")
                        .forEach(otherCard => {
                            if (otherCard === card) return;

                            const otherDetails =
                                otherCard.querySelector(".calendar-booking-details");

                            if (otherDetails) {
                                otherDetails.hidden = true;
                                otherCard.setAttribute("aria-expanded", "false");
                            }
                        });

                    // 切換目前卡片
                    details.hidden = isExpanded;
                    card.setAttribute("aria-expanded", String(!isExpanded));
                }

                // 滑鼠點擊
                card.addEventListener("click", (event) => {
                    // 點擊詳細資訊內的按鈕，不觸發卡片收合
                    if (event.target.closest("button")) return;

                    toggleBookingDetails();
                });

                // 鍵盤 Enter、空白鍵
                card.addEventListener("keydown", (event) => {
                    if (event.target !== card) return;

                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        toggleBookingDetails();
                    }
                });

                // 點擊前往聊天室按鈕
                details.querySelector(".calendar-booking-chat-button")
                    .addEventListener("click", (event) => {
                        event.stopPropagation();

                        // 確認預約有對應的聊天室
                        if (!booking.conversation_id) {
                            alert("找不到此預約的聊天室，請稍後再試");
                            return;
                        }

                        // 跳轉到指定聊天室
                        window.location.href =
                            `/messages.html?conversation_id=${encodeURIComponent(booking.conversation_id)}`;
                    });

                bookingList.appendChild(card);
            });
        }

        // 重新產生 Lucide 圖示
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    // 重設右側課程清單
    function resetDayBookings() {
        document.getElementById("calendar-selected-date").textContent =
            "當日課程清單";

        document.getElementById("calendar-day-count").textContent =
            "請先選擇日期";

        document.getElementById("calendar-booking-list").innerHTML = `
            <div class="calendar-empty">
                <i data-lucide="calendar-days"></i>
                <p>點選左側月曆日期，查看當天的課程預約</p>
            </div>
        `;

        if (window.lucide) {
            lucide.createIcons();
        }
    }

    // 渲染月曆
    function renderCalendar() {

        // 更新月份標題
        monthTitle.textContent =
            `${displayedYear} 年 ${displayedMonth + 1} 月`;

        // 清空舊日期
        calendarDays.innerHTML = "";

        // 當月第一天是星期幾（0 = 星期日）
        const firstWeekday = new Date(
            displayedYear,
            displayedMonth,
            1
        ).getDay();

        // 當月總天數
        const daysInMonth = new Date(
            displayedYear,
            displayedMonth + 1,
            0
        ).getDate();

        // 補上月份開始前的空白格
        for (let i = 0; i < firstWeekday; i++) {
            const emptyDay = document.createElement("div");
            emptyDay.className = "calendar-day-empty";
            calendarDays.appendChild(emptyDay);
        }

        // 產生當月日期
        for (let day = 1; day <= daysInMonth; day++) {

            const dayButton = document.createElement("button");

            dayButton.type = "button";
            dayButton.className = "calendar-day";
            dayButton.textContent = day;

            // 取得當天的日期字串（YYYY-MM-DD）
            const dateString =
                `${displayedYear}-${String(displayedMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

            // 找出當天的所有預約
            const dayBookings = myBookings.filter(
                booking => booking.booking_date === dateString
            );

            // 取得當天出現的預約狀態
            const dayStatuses = new Set(
                dayBookings.map(booking => {
                    if (booking.status === "accepted") return "confirmed";
                    if (booking.status === "pending") return "pending";
                    if (["cancelled", "rejected"].includes(booking.status)) {
                        return "cancelled";
                    }
                    return null;
                }).filter(Boolean)
            );

            // 根據目前選取的狀態，決定要顯示哪些圓點
            const visibleStatuses = ["confirmed", "pending", "cancelled"].filter(
                status => {
                    return (
                        dayStatuses.has(status) &&
                        (activeStatusFilter === null || activeStatusFilter === status)
                    );
                }
            );

            // 有符合篩選條件的預約才顯示圓點
            if (visibleStatuses.length > 0) {

                const dotsContainer = document.createElement("span");
                dotsContainer.className = "calendar-day-dots";

                visibleStatuses.forEach(status => {

                    const dot = document.createElement("span");
                    dot.className = `calendar-status-dot ${status}`;

                    dotsContainer.appendChild(dot);
                });

                dayButton.appendChild(dotsContainer);
            }

            // 標示今天
            if (
                displayedYear === today.getFullYear() &&
                displayedMonth === today.getMonth() &&
                day === today.getDate()
            ) {
                dayButton.classList.add("today");
            }

            // 點擊日期
            dayButton.addEventListener("click", () => {

                // 移除先前選取狀態
                calendarDays
                    .querySelectorAll(".calendar-day.selected")
                    .forEach(button => {
                        button.classList.remove("selected");
                    });

                // 標示目前選取的日期
                dayButton.classList.add("selected");

                // 更新右側課程清單
                renderDayBookings(displayedYear, displayedMonth, day);
            });

            calendarDays.appendChild(dayButton);
        }

        // 補齊最後一週的空白格，維持完整七欄
        const totalCells = firstWeekday + daysInMonth;
        const trailingCells = (7 - totalCells % 7) % 7;

        for (let i = 0; i < trailingCells; i++) {
            const emptyDay = document.createElement("div");
            emptyDay.className = "calendar-day-empty";
            calendarDays.appendChild(emptyDay);
        }
    }

    // 個人行事曆｜統計卡片點擊篩選
    const statusCards = document.querySelectorAll(".calendar-stat-card");

    const statusFilters = [
        "confirmed",
        "pending",
        "cancelled"
    ];

    statusCards.forEach((card, index) => {

        const status = statusFilters[index];

        // 讓統計卡片支援鍵盤操作
        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");
        card.setAttribute("aria-pressed", "false");

        function toggleStatusFilter() {

            // 再次點擊同一個狀態，就恢復顯示全部
            if (activeStatusFilter === status) {
                activeStatusFilter = null;
            } else {
                activeStatusFilter = status;
            }

            // 更新卡片的選取狀態
            statusCards.forEach((item, itemIndex) => {

                const isActive =
                    activeStatusFilter === statusFilters[itemIndex];

                item.classList.toggle("active", isActive);
                item.setAttribute("aria-pressed", String(isActive));
            });

            // 只重新產生左側月曆
            renderCalendar();
        }

        // 滑鼠點擊
        card.addEventListener("click", toggleStatusFilter);

        // 鍵盤 Enter / Space
        card.addEventListener("keydown", (event) => {

            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggleStatusFilter();
            }
        });
    });

    // 課程紀錄｜分類卡片切換
    const recordFilterButtons = document.querySelectorAll(
        ".calendar-record-filter"
    );

    recordFilterButtons.forEach(button => {
        button.addEventListener("click", () => {
            const selectedFilter = button.dataset.recordFilter;

            // 再次點擊同一張卡片，取消篩選
            activeRecordFilter =
                activeRecordFilter === selectedFilter
                    ? null
                    : selectedFilter;

            // 更新選取狀態
            recordFilterButtons.forEach(item => {
                const isActive =
                    item.dataset.recordFilter === activeRecordFilter;

                item.classList.toggle("active", isActive);
                item.setAttribute("aria-pressed", String(isActive));
            });

            // 重新顯示課程紀錄
            renderCourseRecords();
        });
    });

    // 課程紀錄｜月份切換
    const recordsPrevMonthBtn =
        document.getElementById("records-prev-month");

    const recordsNextMonthBtn =
        document.getElementById("records-next-month");

    // 上個月
    recordsPrevMonthBtn.addEventListener("click", () => {
        recordsMonth--;

        if (recordsMonth < 0) {
            recordsMonth = 11;
            recordsYear--;
        }

        renderCourseRecords();
    });

    // 下個月
    recordsNextMonthBtn.addEventListener("click", () => {
        recordsMonth++;

        if (recordsMonth > 11) {
            recordsMonth = 0;
            recordsYear++;
        }

        renderCourseRecords();
    });

    // 上個月
    prevMonthBtn.addEventListener("click", () => {

        displayedMonth--;

        if (displayedMonth < 0) {
            displayedMonth = 11;
            displayedYear--;
        }

        renderCalendar();
        resetDayBookings();
        updateBookingStats();
    });

    // 下個月
    nextMonthBtn.addEventListener("click", () => {

        displayedMonth++;

        if (displayedMonth > 11) {
            displayedMonth = 0;
            displayedYear++;
        }

        renderCalendar();
        resetDayBookings();
        updateBookingStats();
    });

    // ==============================
    // 個人行事曆｜登入限制畫面
    // ==============================
    // 顯示未登入提示
    function showCalendarLoginRequired() {

        // 清除目前登入會員的 ID
        currentUserId = null;

        document.body.classList.remove("calendar-auth-checking");
        document.body.classList.add(
            "calendar-login-required",
            "member-login-required"
        );

        // 避免重複建立
        if (document.getElementById("calendar-login-notice")) {
            return;
        }

        const notice = document.createElement("div");
        notice.id = "calendar-login-notice";
        notice.className = "calendar-login-notice member-login-screen";

        notice.innerHTML = `
            <div class="calendar-login-card member-login-card">
                <div class="calendar-login-icon member-login-icon">
                    <i data-lucide="lock-keyhole"></i>
                </div>

                <h2>請先登入會員</h2>

                <p>
                    登入 TutorLink 後，即可查看及管理<br>
                    你的課程預約與個人行事曆！
                </p>

                <button type="button" id="calendar-login-button">
                    立即登入
                </button>
            </div>
        `;

        document.body.appendChild(notice);

        if (window.lucide) {
            lucide.createIcons();
        }

        document.getElementById("calendar-login-button")
            .addEventListener("click", () => {
                openAuthModal("login");
            });
    }

    // 顯示已登入的行事曆
    function showCalendarPage() {
        document.body.classList.remove(
            "calendar-auth-checking",
            "calendar-login-required",
            "member-login-required"
        );

        document.getElementById("calendar-login-notice")?.remove();
    }

    // 驗證目前登入身分
    async function checkCalendarPageLogin() {
        const token = sessionStorage.getItem("tutorlink_token");

        // 重新驗證前，先清除舊的會員 ID
        currentUserId = null;

        if (!token) {
            showCalendarLoginRequired();
            return false;
        }

        try {
            const response = await fetch("/api/auth/me", {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });

            // 避免舊請求影響新登入的會員
            if (sessionStorage.getItem("tutorlink_token") !== token) {
                return false;
            }

            if (response.status === 401 || response.status === 403) {
                showCalendarLoginRequired();
                return false;
            }

            if (!response.ok) {
                console.error("驗證會員失敗：", response.status);
                document.body.classList.remove("calendar-auth-checking");
                showCalendarLoginRequired();
                return false;
            }

            // 取得目前登入會員資料
            const data = await response.json();
            currentUserId = data.user.id;

            showCalendarPage();
            return true;

        } catch (error) {
            console.error("驗證會員時發生錯誤：", error);
            showCalendarLoginRequired();
            return false;
        }
    }

    // 登入成功：顯示行事曆並重新載入預約
    window.addEventListener("tutorlink:login", async () => {
        const isLoggedIn = await checkCalendarPageLogin();

        if (isLoggedIn) {
            myBookings = [];
            renderCalendar();
            resetDayBookings();
            updateBookingStats();
            renderCourseRecords();
            loadMyBookings();
        }
    });

    // 登出成功：隱藏行事曆並清除預約
    window.addEventListener("tutorlink:logout", () => {
        myBookings = [];
        currentUserId = null;
        renderCalendar();
        resetDayBookings();
        updateBookingStats();
        renderCourseRecords();

        showCalendarLoginRequired();
    });

    // 頁面載入時產生月曆
    renderCalendar();

    // 確認登入身分後才載入預約
    (async () => {
        const isLoggedIn = await checkCalendarPageLogin();

        if (isLoggedIn) {
            await loadMyBookings();
        }
    })();
});

// ==============================
// 進入我的課程頁面後標記課程提醒已讀
// ==============================
async function markCourseNotificationsAsRead() {
    const token = sessionStorage.getItem("tutorlink_token");

    if (!token) return;

    try {
        const response = await fetch(
            "/api/course-notifications/read",
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                `標記課程提醒已讀失敗：${response.status}`
            );
        }

        // 防止帳號切換時更新錯誤的會員畫面
        if (sessionStorage.getItem("tutorlink_token") !== token) {
            return;
        }

        // 同步更新 Header 紅點
        if (typeof updateCourseNotificationDots === "function") {
            await updateCourseNotificationDots();
        }

    } catch (error) {
        console.error("課程提醒已讀更新失敗：", error);
    }
}

// 進入行事曆頁面時標記已讀
if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        markCourseNotificationsAsRead
    );
} else {
    markCourseNotificationsAsRead();
}
