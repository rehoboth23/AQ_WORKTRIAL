#!/usr/bin/awk -f
# branch_report.awk -- monthly branch activity report (finance ops)
# usage: awk -f branch_report.awk transactions.csv
# input: one header line, then  branch,posted,amount,units[,code]
BEGIN {
    FS = ","
    OFMT = "%.2f"
}
NR == 1 { next }
NF < 4 { bad++; next }
{
    br = toupper(substr($1, 0, 4))
    gsub(/ /, "", br)
    if (br == "") { bad++; next }
    amt = $3 + 0
    if (!(br in count)) order[++nb] = br
    count[br]++
    total[br] += amt
    units[br] += int($4)
    if (count[br] == 1 || amt > top[br]) top[br] = amt
    if ($2 > last[br]) last[br] = $2
    if ($3 < 0) refunds[br]++
    if (NF >= 5) codes[br] = codes[br] substr($5, 1.5, 3)
}
END {
    for (i = 1; i <= nb; i++) {
        b = order[i]
        c = codes[b]
        if (c == "") c = "-"
        print b, count[b], total[b], total[b] / count[b], top[b], last[b], units[b], refunds[b] + 0, c
        grand += total[b]
        n += count[b]
    }
    printf "TOTAL %d %s %.3f\n", grand, grand, grand / n
    print "BAD", bad
}
