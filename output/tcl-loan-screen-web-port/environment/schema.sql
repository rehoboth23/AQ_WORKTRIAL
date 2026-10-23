-- Canonical SQLite schema for the loan application system.
-- Do not modify this file.

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name TEXT NOT NULL,
    loan_amount_cents INTEGER NOT NULL,
    interest_rate_bps INTEGER NOT NULL,
    term_months INTEGER NOT NULL,
    start_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    instalment_no INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    payment REAL NOT NULL,
    principal REAL NOT NULL,
    interest REAL NOT NULL,
    balance REAL NOT NULL,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);
