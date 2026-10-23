# loanapp.tcl - Legacy Tcl/Tk Loan Application Screen
# Regional Credit Union - Originally deployed 2004
#
# Defines validation, repayment calculation, and database helpers.
# Sourced by the test driver to compute reference values.

# ---------------------------------------------------------------------------
# Utility procedures
# ---------------------------------------------------------------------------

proc last_day_of_month {month year} {
    set days_in_month {31 28 31 30 31 30 31 31 30 31 30 31 31}
    set d [lindex $days_in_month [expr {$month - 1}]]
    if {$month == 2} {
        if {($year % 4 == 0 && $year % 100 != 0) || ($year % 400 == 0)} {
            set d 29
        }
    }
    return $d
}

proc add_months {date n} {
    set day   [scan [string range $date 0 1] %d]
    set month [scan [string range $date 3 4] %d]
    set year  [scan [string range $date 6 9] %d]

    set new_month [expr {$month + $n}]
    set new_year  $year
    while {$new_month > 12} {
        set new_month [expr {$new_month - 12}]
        incr new_year
    }
    while {$new_month < 1} {
        set new_month [expr {$new_month + 12}]
        incr new_year -1
    }

    set last [last_day_of_month $new_month $new_year]
    if {$day > $last} {
        set day $last
    }

    return [format "%02d/%02d/%04d" $day $new_month $new_year]
}

proc format_currency {amount} {
    set formatted [format "%.2f" $amount]
    set parts [split $formatted "."]
    set int_part [lindex $parts 0]
    set dec_part [lindex $parts 1]

    set negative 0
    if {[string index $int_part 0] == "-"} {
        set negative 1
        set int_part [string range $int_part 1 end]
    }

    set result ""
    set len [string length $int_part]
    set pos 0
    while {$pos < $len} {
        if {$pos > 0 && ($len - $pos) % 3 == 0} {
            append result ","
        }
        append result [string index $int_part $pos]
        incr pos
    }

    if {$negative} {
        set result "-$result"
    }

    return "\$$result.$dec_part"
}

proc format_rate {rate} {
    return [format "%.2f%%" $rate]
}

# ---------------------------------------------------------------------------
# Validation procedure
# Field priority: applicant_name -> loan_amount -> interest_rate
#                 -> term_months -> start_date
# Within each field, rules are checked in source order.
# Returns the first error message (with trailing period), or "" if valid.
# ---------------------------------------------------------------------------

proc validate {name amount rate term start_date} {
    # --- Applicant name ---
    if {$name eq ""} {
        return "Applicant name is required."
    }
    if {[string length $name] < 2} {
        return "Applicant name must be at least 2 characters."
    }
    if {![regexp {^[A-Za-z][A-Za-z \-']*$} $name]} {
        return "Applicant name contains invalid characters."
    }

    # --- Loan amount ---
    if {$amount eq ""} {
        return "Loan amount is required."
    }
    if {![string is double $amount]} {
        return "Loan amount must be a positive number."
    }
    set amt [expr {double($amount)}]
    if {$amt <= 0} {
        return "Loan amount must be a positive number."
    }
    if {$amt < 500} {
        return "Loan amount must be at least \$500."
    }
    if {$amt > 500000} {
        return "Loan amount must not exceed \$500,000."
    }

    # --- Interest rate ---
    if {$rate eq ""} {
        return "Interest rate is required."
    }
    if {![string is double $rate]} {
        return "Interest rate must be a number between 0 and 30."
    }
    set rt [expr {double($rate)}]
    if {$rt <= 0 || $rt >= 30} {
        return "Interest rate must be a number between 0 and 30."
    }

    # --- Term months ---
    if {$term eq ""} {
        return "Loan term is required."
    }
    if {![regexp {^[0-9]+$} $term]} {
        return "Loan term must be a whole number of months."
    }
    set tm [expr {int($term)}]
    if {$tm < 6 || $tm > 360} {
        return "Loan term must be between 6 and 360 months."
    }

    # --- Start date ---
    if {$start_date eq ""} {
        return "Start date is required."
    }
    if {![regexp {^[0-9]{2}/[0-9]{2}/[0-9]{4}$} $start_date]} {
        return "Start date must be in DD/MM/YYYY format."
    }
    set day   [scan [string range $start_date 0 1] %d]
    set month [scan [string range $start_date 3 4] %d]
    set year  [scan [string range $start_date 6 9] %d]

    if {$month < 1 || $month > 12} {
        return "Start date must be in DD/MM/YYYY format."
    }
    set last [last_day_of_month $month $year]
    if {$day < 1 || $day > $last} {
        return "Start date must be in DD/MM/YYYY format."
    }

    # Minimum start date: 01/01/2025
    if {$year < 2025} {
        return "Start date must be on or after 01/01/2025."
    }

    return ""
}

# ---------------------------------------------------------------------------
# Repayment calculation procedure
# Per-step rounding with format("%.2f") on every intermediate value.
# Last instalment: principal = remaining balance, payment recalculated.
# Returns a dict with monthly_payment, total_repayment, total_interest,
# and schedule (list of dicts).
# ---------------------------------------------------------------------------

proc calculate_repayment {amount rate term start_date} {
    set principal    [expr {double($amount)}]
    set annual_rate  [expr {double($rate)}]
    set monthly_rate [expr {$annual_rate / 100.0 / 12.0}]

    set monthly_payment [format "%.2f" [expr {$principal * $monthly_rate / (1 - pow(1 + $monthly_rate, -$term))}]]

    set balance $principal
    set schedule {}
    set total_payment 0.0
    set total_interest 0.0

    for {set i 1} {$i <= $term} {incr i} {
        set interest [format "%.2f" [expr {$balance * $monthly_rate}]]

        if {$i == $term} {
            set principal_part $balance
            set payment [format "%.2f" [expr {$principal_part + $interest}]]
        } else {
            set principal_part [format "%.2f" [expr {$monthly_payment - $interest}]]
            set payment $monthly_payment
        }

        set balance [format "%.2f" [expr {$balance - $principal_part}]]

        set payment_date [add_months $start_date $i]

        lappend schedule [dict create \
            instalment_no $i \
            payment_date  $payment_date \
            payment       $payment \
            principal     $principal_part \
            interest      $interest \
            balance       $balance]

        set total_payment  [expr {$total_payment + $payment}]
        set total_interest [expr {$total_interest + $interest}]
    }

    set total_repayment [format "%.2f" $total_payment]
    set total_interest  [format "%.2f" $total_interest]

    return [dict create \
        monthly_payment  $monthly_payment \
        total_repayment  $total_repayment \
        total_interest   $total_interest \
        schedule         $schedule]
}

# ---------------------------------------------------------------------------
# Database format helper
# ---------------------------------------------------------------------------

proc compute_db_format {amount rate start_date} {
    set cents [expr {int(round($amount * 100))}]
    set bps   [expr {int(round($rate * 100))}]
    return [dict create \
        loan_amount_cents  $cents \
        interest_rate_bps  $bps \
        start_date         $start_date]
}
