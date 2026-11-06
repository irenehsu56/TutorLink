// ==============================
// 家教預約系統：共用預約視窗
// ==============================
// 預約錯誤｜顯示共用錯誤通知視窗
window.showBookingErrorModal = function (message) {
    return new Promise((resolve) => {
        const modal = document.getElementById("booking-error-modal");
        const messageElement = document.getElementById("booking-error-message");
        const closeButton = document.getElementById("booking-error-close");

        if (!modal || !messageElement || !closeButton) {
            console.error("找不到預約錯誤通知視窗");
            resolve();
            return;
        }

        const overlay = modal.querySelector(".booking-modal-overlay");

        messageElement.textContent = message;
        modal.hidden = false;

        function closeModal() {
            modal.hidden = true;

            closeButton.removeEventListener("click", closeModal);
            overlay?.removeEventListener("click", closeModal);
            document.removeEventListener("keydown", handleKeydown);

            resolve();
        }

        function handleKeydown(event) {
            if (event.key === "Escape") {
                closeModal();
            }
        }

        closeButton.addEventListener("click", closeModal);
        overlay?.addEventListener("click", closeModal);
        document.addEventListener("keydown", handleKeydown);

        closeButton.focus();
    });
};

// ==============================
// 家教預約系統：老師拒絕預約確認視窗
// ==============================
window.showBookingRejectModal = function () {
    return new Promise((resolve) => {
        const modal = document.getElementById("booking-reject-modal");
        const cancelButton = document.getElementById("booking-reject-cancel");
        const confirmButton = document.getElementById("booking-reject-confirm");

        if (!modal || !cancelButton || !confirmButton) {
            console.error("找不到拒絕預約確認視窗");
            resolve(false);
            return;
        }

        const overlay = modal.querySelector(".booking-modal-overlay");

        modal.hidden = false;

        if (window.lucide) {
            lucide.createIcons();
        }

        function closeModal(confirmed) {
            modal.hidden = true;

            cancelButton.removeEventListener("click", handleCancel);
            confirmButton.removeEventListener("click", handleConfirm);
            overlay?.removeEventListener("click", handleCancel);
            document.removeEventListener("keydown", handleKeydown);

            resolve(confirmed);
        }

        function handleCancel() {
            closeModal(false);
        }

        function handleConfirm() {
            closeModal(true);
        }

        function handleKeydown(event) {
            if (event.key === "Escape") {
                closeModal(false);
            }
        }

        cancelButton.addEventListener("click", handleCancel);
        confirmButton.addEventListener("click", handleConfirm);
        overlay?.addEventListener("click", handleCancel);
        document.addEventListener("keydown", handleKeydown);

        cancelButton.focus();
    });
};

// ==============================
// 家教預約系統：學生取消預約確認視窗
// ==============================
window.showBookingCancelModal = function () {
    return new Promise((resolve) => {
        const modal = document.getElementById("booking-cancel-modal");
        const backButton = document.getElementById("booking-cancel-back");
        const confirmButton = document.getElementById("booking-cancel-confirm");

        if (!modal || !backButton || !confirmButton) {
            console.error("找不到取消預約確認視窗");
            resolve(false);
            return;
        }

        const overlay = modal.querySelector(".booking-modal-overlay");

        modal.hidden = false;

        if (window.lucide) {
            lucide.createIcons();
        }

        function closeModal(confirmed) {
            modal.hidden = true;

            backButton.removeEventListener("click", handleBack);
            confirmButton.removeEventListener("click", handleConfirm);
            overlay?.removeEventListener("click", handleBack);
            document.removeEventListener("keydown", handleKeydown);

            resolve(confirmed);
        }

        function handleBack() {
            closeModal(false);
        }

        function handleConfirm() {
            closeModal(true);
        }

        function handleKeydown(event) {
            if (event.key === "Escape") {
                closeModal(false);
            }
        }

        backButton.addEventListener("click", handleBack);
        confirmButton.addEventListener("click", handleConfirm);
        overlay?.addEventListener("click", handleBack);
        document.addEventListener("keydown", handleKeydown);

        backButton.focus();
    });
};