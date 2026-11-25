"""Queries for the existing append-only case audit."""
import json

PAGE_SIZE = 50


def case_events(connection, case_id, query="", before=None, limit=PAGE_SIZE):
    sql = """
        SELECT audit.sequence, audit.timestamp, audit.action, operators.name AS operator,
               audit.details, audit.operator_id, archive_events.provenance
        FROM audit JOIN operators ON operators.id = audit.operator_id
        LEFT JOIN archive_events ON archive_events.sequence = audit.sequence
        WHERE audit.case_id = ?
    """
    arguments = [case_id]
    if query:
        sql += " AND instr(lower(audit.action || ' ' || coalesce(json_extract(archive_events.provenance, '$.operator'), operators.name)), lower(?)) > 0"
        arguments.append(query)
    if before is not None:
        sql += " AND audit.sequence < ?"
        arguments.append(before)
    if limit is not None:
        sql += " ORDER BY audit.sequence DESC LIMIT ?"
        arguments.append(limit)
    else:
        sql += " ORDER BY audit.sequence"
    events = []
    for row in connection.execute(sql, arguments):
        event = dict(row)
        if raw := event.pop("provenance"):
            provenance = json.loads(raw)
            event["operator"] = provenance["operator"]
            event["provenance"] = provenance
        events.append(event)
    return events
