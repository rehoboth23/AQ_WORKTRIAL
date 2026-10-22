The warehouse audit export tool in /app exports inventory transactions from /app/warehouse.db to a CSV file. It supports --checkpoint and --resume so long-running exports can be stopped and continued later.

The problem: when an export is interrupted and then resumed, the resulting CSV file differs from what a single uninterrupted run would produce.

Fix the tool so that a resumed export always produces exactly the same output as an uninterrupted export: the same header row, the same transaction rows in the same order with the same balance values, and the same summary section. This must hold regardless of when the export is interrupted and resumed.
