# PostgreSQL to SQLite Migration Notes

## General Differences

### Type Coercion
PostgreSQL has strict type checking. SQLite uses dynamic typing (type
affinity). Most queries work identically, but be aware of implicit type
conversions. For example, SQLite may treat a string that looks like a
number as a number in arithmetic contexts.

### NULL Handling
Both PostgreSQL and SQLite treat NULL similarly in most contexts:

- `SUM(column)` returns NULL if all input values are NULL (both databases)
- `NULL = NULL` evaluates to NULL (not TRUE) in both databases
- `INNER JOIN` naturally excludes NULL keys in both databases
- `LEFT JOIN` preserves rows from the left table even when the join key
  is NULL on the right side

However, NULL propagation through cascading views or computed columns
can produce unexpected results. Always use `COALESCE` when a column must
have a non-NULL default value.

### Date Functions
PostgreSQL has rich date/time support including `AT TIME ZONE`. SQLite's
date functions use modifier strings:

- `date(column)` extracts the date part
- `date(column, '+N hours')` or `date(column, '-N hours')` adjusts time
- `strftime(format, column)` for custom formatting

When migrating timezone-dependent logic, replace `AT TIME ZONE` with the
appropriate `date()` modifier using the UTC offset.

### Boolean Type
PostgreSQL has a native BOOLEAN type. SQLite stores booleans as INTEGER
(0/1). Queries using boolean columns should use 0/1 comparisons in SQLite.

### JOIN Behavior
Both databases handle JOINs identically for non-NULL keys. When join keys
can be NULL, the choice of INNER JOIN vs LEFT JOIN matters:

- `INNER JOIN` excludes rows where the join key is NULL on either side
- `LEFT JOIN` preserves all rows from the left table

If the business logic requires including rows with NULL join keys, use
`LEFT JOIN` and adjust the WHERE clause accordingly.

### Common Pitfalls
1. **String concatenation**: PostgreSQL uses `||` (same as SQLite) or
   `CONCAT()`. SQLite only supports `||`.
2. **Array types**: PostgreSQL supports arrays. SQLite does not. Use JSON
   or separate tables.
3. **Full-text search**: PostgreSQL has built-in FTS. SQLite requires the
   FTS5 extension.
4. **JSON**: PostgreSQL has native JSONB. SQLite has JSON1 extension
   (usually available).
5. **Sequences**: PostgreSQL uses sequences for auto-increment. SQLite
   uses `INTEGER PRIMARY KEY` with or without `AUTOINCREMENT`.
