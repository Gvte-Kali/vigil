"""Queries for the existing append-only case audit."""
PAGE_SIZE = 50


def case_events(connection, case_id, query="", before=None, limit=PAGE_SIZE):
    sql = """
        SELECT audit.sequence, audit.timestamp, audit.action, operators.name AS operator,
               audit.details
        FROM audit JOIN operators ON operators.id = audit.operator_id
        WHERE audit.case_id = ?
    """
    arguments = [case_id]
    if query:
        sql += " AND instr(lower(audit.action || ' ' || operators.name), lower(?)) > 0"
        arguments.append(query)
    if before is not None:
        sql += " AND audit.sequence < ?"
        arguments.append(before)
    if limit is not None:
        sql += " ORDER BY audit.sequence DESC LIMIT ?"
        arguments.append(limit)
    else:
        sql += " ORDER BY audit.sequence"
    return [dict(row) for row in connection.execute(sql, arguments)]
