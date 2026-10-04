"""Add timing fields without deleting existing event data."""
from sqlalchemy import inspect, text

def migrate_timing(engine):
    timestamp="TIMESTAMP WITH TIME ZONE" if engine.dialect.name=="postgresql" else "DATETIME"
    additions={"competition":{"ended_at":timestamp,"paused_duration":"FLOAT"},"teams":{"elapsed_seconds":"FLOAT","exit_count":"INTEGER NOT NULL DEFAULT 0","eliminated_at":timestamp},"door_completions":{"elapsed_seconds":"FLOAT"}}
    with engine.begin() as connection:
        if engine.dialect.name=="postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(38472915)"))
        for table,columns in additions.items():
            existing={column["name"] for column in inspect(connection).get_columns(table)}
            for column,kind in columns.items():
                if column not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {kind}'))
        connection.execute(text("UPDATE competition SET paused_duration=COALESCE(paused_seconds,0) WHERE paused_duration IS NULL"))
        connection.execute(text("""UPDATE competition SET ended_at=(
            SELECT MAX(created_at) FROM audit_logs WHERE action='competition.phase.FINISHED'
        ) WHERE phase='FINISHED' AND ended_at IS NULL"""))
