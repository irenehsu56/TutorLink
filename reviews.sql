
CREATE TABLE reviews (
    id INT NOT NULL AUTO_INCREMENT,
    booking_id INT NOT NULL,
    student_id INT NOT NULL,
    teacher_id INT NOT NULL,

    content TEXT NOT NULL,
    teacher_reply TEXT DEFAULT NULL,
    teacher_replied_at DATETIME DEFAULT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_reviews_booking (booking_id),
    KEY idx_reviews_teacher (teacher_id, created_at),
    KEY idx_reviews_student (student_id),

    CONSTRAINT fk_reviews_booking
        FOREIGN KEY (booking_id)
        REFERENCES bookings(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_reviews_student
        FOREIGN KEY (student_id)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_reviews_teacher
        FOREIGN KEY (teacher_id)
        REFERENCES teachers(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_reviews_content
        CHECK (CHAR_LENGTH(TRIM(content)) > 0),

    CONSTRAINT chk_reviews_reply
        CHECK (
            teacher_reply IS NULL
            OR CHAR_LENGTH(TRIM(teacher_reply)) > 0
        )
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;
