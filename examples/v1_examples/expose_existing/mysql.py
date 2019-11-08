# Failed to get col type for columns_priv.Column_priv
# Failed to get col type for event.sql_mode
# Failed to get col type for general_log.user_host
# Failed to get col type for proc.sql_mode
# Failed to get col type for procs_priv.Proc_priv
# Failed to get col type for slow_log.user_host
# Failed to get col type for tables_priv.Table_priv
# Failed to get col type for tables_priv.Column_priv
# coding: utf-8
from sqlalchemy import (
    BIGINT,
    CHAR,
    Column,
    DateTime,
    Enum,
    Float,
    INTEGER,
    LargeBinary,
    SMALLINT,
    String,
    TEXT,
    TIME,
    TIMESTAMP,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.mysql.enumerated import ENUM, SET
from sqlalchemy.dialects.mysql.types import LONGBLOB, MEDIUMBLOB, MEDIUMTEXT, TINYINT
from sqlalchemy.ext.declarative import declarative_base


########################################################################################################################
# Manually Added for safrs, TODO: improve this crap
#

Base = db.Model
metadata = Base.metadata


def BIGINT(_):
    return db.SMALLINT


def SMALLINT(_):
    return db.SMALLINT


def INTEGER(_):
    return db.INTEGER


def TIME(**kwargs):
    return db.TIME


TIMESTAMP = db.TIMESTAMP
NullType = db.String

########################################################################################################################


class ColumnsPriv(SAFRSBase, Base):
    __tablename__ = "columns_priv"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Db = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Table_name = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Column_name = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Timestamp = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    Column_priv = Column(SET, nullable=False, server_default=text("''"))


class Db(SAFRSBase, Base):
    __tablename__ = "db"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Db = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, index=True, server_default=text("''"))
    Select_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Insert_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Update_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Delete_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Drop_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Grant_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    References_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Index_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Alter_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_tmp_table_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Lock_tables_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_view_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Show_view_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_routine_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Alter_routine_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Execute_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Event_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Trigger_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))


class EngineCost(SAFRSBase, Base):
    __tablename__ = "engine_cost"

    engine_name = Column(String(64), primary_key=True, nullable=False)
    device_type = Column(INTEGER(11), primary_key=True, nullable=False)
    cost_name = Column(String(64), primary_key=True, nullable=False)
    cost_value = Column(Float)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    comment = Column(String(1024))


class Event(SAFRSBase, Base):
    __tablename__ = "event"

    db = Column(CHAR(64), primary_key=True, nullable=False, server_default=text("''"))
    name = Column(CHAR(64), primary_key=True, nullable=False, server_default=text("''"))
    body = Column(LONGBLOB, nullable=False)
    definer = Column(CHAR(93), nullable=False, server_default=text("''"))
    execute_at = Column(DateTime)
    interval_value = Column(INTEGER(11))
    interval_field = Column(
        Enum(
            "YEAR",
            "QUARTER",
            "MONTH",
            "DAY",
            "HOUR",
            "MINUTE",
            "WEEK",
            "SECOND",
            "MICROSECOND",
            "YEAR_MONTH",
            "DAY_HOUR",
            "DAY_MINUTE",
            "DAY_SECOND",
            "HOUR_MINUTE",
            "HOUR_SECOND",
            "MINUTE_SECOND",
            "DAY_MICROSECOND",
            "HOUR_MICROSECOND",
            "MINUTE_MICROSECOND",
            "SECOND_MICROSECOND",
        )
    )
    created = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    modified = Column(TIMESTAMP, nullable=False, server_default=text("'0000-00-00 00:00:00'"))
    last_executed = Column(DateTime)
    starts = Column(DateTime)
    ends = Column(DateTime)
    status = Column(Enum("ENABLED", "DISABLED", "SLAVESIDE_DISABLED"), nullable=False, server_default=text("'ENABLED'"))
    on_completion = Column(Enum("DROP", "PRESERVE"), nullable=False, server_default=text("'DROP'"))
    sql_mode = Column(SET, nullable=False, server_default=text("''"))
    comment = Column(CHAR(64), nullable=False, server_default=text("''"))
    originator = Column(INTEGER(10), nullable=False)
    time_zone = Column(CHAR(64), nullable=False, server_default=text("'SYSTEM'"))
    character_set_client = Column(CHAR(32))
    collation_connection = Column(CHAR(32))
    db_collation = Column(CHAR(32))
    body_utf8 = Column(LONGBLOB)


class Func(SAFRSBase, Base):
    __tablename__ = "func"

    name = Column(CHAR(64, "utf8_bin"), primary_key=True, server_default=text("''"))
    ret = Column(TINYINT(1), nullable=False, server_default=text("'0'"))
    dl = Column(CHAR(128, "utf8_bin"), nullable=False, server_default=text("''"))
    type = Column(ENUM("function", "aggregate"), nullable=False)


t_general_log = Table(
    "general_log",
    metadata,
    # Column('event_time', TIMESTAMP(fsp=6), nullable=False, server_default=text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)")),
    #
    # MANUAL EDIT:
    Column("event_time", TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)")),
    Column("user_host", MEDIUMTEXT, nullable=False),
    Column("thread_id", BIGINT(21), nullable=False),
    Column("server_id", INTEGER(10), nullable=False),
    Column("command_type", String(64), nullable=False),
    Column("argument", MEDIUMBLOB, nullable=False),
)


class GtidExecuted(SAFRSBase, Base):
    __tablename__ = "gtid_executed"

    source_uuid = Column(CHAR(36), primary_key=True, nullable=False)
    interval_start = Column(BIGINT(20), primary_key=True, nullable=False)
    interval_end = Column(BIGINT(20), nullable=False)


class HelpCategory(SAFRSBase, Base):
    __tablename__ = "help_category"

    help_category_id = Column(SMALLINT(5), primary_key=True)
    name = Column(CHAR(64), nullable=False, unique=True)
    parent_category_id = Column(SMALLINT(5))
    url = Column(Text, nullable=False)


class HelpKeyword(SAFRSBase, Base):
    __tablename__ = "help_keyword"

    help_keyword_id = Column(INTEGER(10), primary_key=True)
    name = Column(CHAR(64), nullable=False, unique=True)


class HelpRelation(SAFRSBase, Base):
    __tablename__ = "help_relation"

    help_topic_id = Column(INTEGER(10), primary_key=True, nullable=False)
    help_keyword_id = Column(INTEGER(10), primary_key=True, nullable=False)


class HelpTopic(SAFRSBase, Base):
    __tablename__ = "help_topic"

    help_topic_id = Column(INTEGER(10), primary_key=True)
    name = Column(CHAR(64), nullable=False, unique=True)
    help_category_id = Column(SMALLINT(5), nullable=False)
    description = Column(Text, nullable=False)
    example = Column(Text, nullable=False)
    url = Column(Text, nullable=False)


class InnodbIndexStat(SAFRSBase, Base):
    __tablename__ = "innodb_index_stats"

    database_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    table_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    index_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    stat_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    stat_value = Column(BIGINT(20), nullable=False)
    sample_size = Column(BIGINT(20))
    stat_description = Column(String(1024, "utf8_bin"), nullable=False)


class InnodbTableStat(SAFRSBase, Base):
    __tablename__ = "innodb_table_stats"

    database_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    table_name = Column(String(64, "utf8_bin"), primary_key=True, nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    n_rows = Column(BIGINT(20), nullable=False)
    clustered_index_size = Column(BIGINT(20), nullable=False)
    sum_of_other_index_sizes = Column(BIGINT(20), nullable=False)


class NdbBinlogIndex(SAFRSBase, Base):
    __tablename__ = "ndb_binlog_index"

    Position = Column(BIGINT(20), nullable=False)
    File = Column(String(255), nullable=False)
    epoch = Column(BIGINT(20), primary_key=True, nullable=False)
    inserts = Column(INTEGER(10), nullable=False)
    updates = Column(INTEGER(10), nullable=False)
    deletes = Column(INTEGER(10), nullable=False)
    schemaops = Column(INTEGER(10), nullable=False)
    orig_server_id = Column(INTEGER(10), primary_key=True, nullable=False)
    orig_epoch = Column(BIGINT(20), primary_key=True, nullable=False)
    gci = Column(INTEGER(10), nullable=False)
    next_position = Column(BIGINT(20), nullable=False)
    next_file = Column(String(255), nullable=False)


class Plugin(SAFRSBase, Base):
    __tablename__ = "plugin"

    name = Column(String(64), primary_key=True, server_default=text("''"))
    dl = Column(String(128), nullable=False, server_default=text("''"))


class Proc(SAFRSBase, Base):
    __tablename__ = "proc"

    db = Column(CHAR(64), primary_key=True, nullable=False, server_default=text("''"))
    name = Column(CHAR(64), primary_key=True, nullable=False, server_default=text("''"))
    type = Column(Enum("FUNCTION", "PROCEDURE"), primary_key=True, nullable=False)
    specific_name = Column(CHAR(64), nullable=False, server_default=text("''"))
    language = Column(Enum("SQL"), nullable=False, server_default=text("'SQL'"))
    sql_data_access = Column(
        Enum("CONTAINS_SQL", "NO_SQL", "READS_SQL_DATA", "MODIFIES_SQL_DATA"), nullable=False, server_default=text("'CONTAINS_SQL'")
    )
    is_deterministic = Column(Enum("YES", "NO"), nullable=False, server_default=text("'NO'"))
    security_type = Column(Enum("INVOKER", "DEFINER"), nullable=False, server_default=text("'DEFINER'"))
    param_list = Column(LargeBinary, nullable=False)
    returns = Column(LONGBLOB, nullable=False)
    body = Column(LONGBLOB, nullable=False)
    definer = Column(CHAR(93), nullable=False, server_default=text("''"))
    created = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    modified = Column(TIMESTAMP, nullable=False, server_default=text("'0000-00-00 00:00:00'"))
    sql_mode = Column(SET, nullable=False, server_default=text("''"))
    comment = Column(TEXT, nullable=False)
    character_set_client = Column(CHAR(32))
    collation_connection = Column(CHAR(32))
    db_collation = Column(CHAR(32))
    body_utf8 = Column(LONGBLOB)


class ProcsPriv(SAFRSBase, Base):
    __tablename__ = "procs_priv"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Db = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Routine_name = Column(CHAR(64), primary_key=True, nullable=False, server_default=text("''"))
    Routine_type = Column(ENUM("FUNCTION", "PROCEDURE"), primary_key=True, nullable=False)
    Grantor = Column(CHAR(93, "utf8_bin"), nullable=False, index=True, server_default=text("''"))
    Proc_priv = Column(SET, nullable=False, server_default=text("''"))
    Timestamp = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class ProxiesPriv(SAFRSBase, Base):
    __tablename__ = "proxies_priv"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Proxied_host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Proxied_user = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    With_grant = Column(TINYINT(1), nullable=False, server_default=text("'0'"))
    Grantor = Column(CHAR(93, "utf8_bin"), nullable=False, index=True, server_default=text("''"))
    Timestamp = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class ServerCost(SAFRSBase, Base):
    __tablename__ = "server_cost"

    cost_name = Column(String(64), primary_key=True)
    cost_value = Column(Float)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    comment = Column(String(1024))


class Server(SAFRSBase, Base):
    __tablename__ = "servers"

    Server_name = Column(CHAR(64), primary_key=True, server_default=text("''"))
    Host = Column(CHAR(64), nullable=False, server_default=text("''"))
    Db = Column(CHAR(64), nullable=False, server_default=text("''"))
    Username = Column(CHAR(64), nullable=False, server_default=text("''"))
    Password = Column(CHAR(64), nullable=False, server_default=text("''"))
    Port = Column(INTEGER(4), nullable=False, server_default=text("'0'"))
    Socket = Column(CHAR(64), nullable=False, server_default=text("''"))
    Wrapper = Column(CHAR(64), nullable=False, server_default=text("''"))
    Owner = Column(CHAR(64), nullable=False, server_default=text("''"))


class SlaveMasterInfo(SAFRSBase, Base):
    __tablename__ = "slave_master_info"

    Number_of_lines = Column(INTEGER(10), nullable=False)
    Master_log_name = Column(TEXT, nullable=False)
    Master_log_pos = Column(BIGINT(20), nullable=False)
    Host = Column(CHAR(64))
    User_name = Column(TEXT)
    User_password = Column(TEXT)
    Port = Column(INTEGER(10), nullable=False)
    Connect_retry = Column(INTEGER(10), nullable=False)
    Enabled_ssl = Column(TINYINT(1), nullable=False)
    Ssl_ca = Column(TEXT)
    Ssl_capath = Column(TEXT)
    Ssl_cert = Column(TEXT)
    Ssl_cipher = Column(TEXT)
    Ssl_key = Column(TEXT)
    Ssl_verify_server_cert = Column(TINYINT(1), nullable=False)
    Heartbeat = Column(Float, nullable=False)
    Bind = Column(TEXT)
    Ignored_server_ids = Column(TEXT)
    Uuid = Column(TEXT)
    Retry_count = Column(BIGINT(20), nullable=False)
    Ssl_crl = Column(TEXT)
    Ssl_crlpath = Column(TEXT)
    Enabled_auto_position = Column(TINYINT(1), nullable=False)
    Channel_name = Column(CHAR(64), primary_key=True)
    Tls_version = Column(TEXT)


class SlaveRelayLogInfo(SAFRSBase, Base):
    __tablename__ = "slave_relay_log_info"

    Number_of_lines = Column(INTEGER(10), nullable=False)
    Relay_log_name = Column(TEXT, nullable=False)
    Relay_log_pos = Column(BIGINT(20), nullable=False)
    Master_log_name = Column(TEXT, nullable=False)
    Master_log_pos = Column(BIGINT(20), nullable=False)
    Sql_delay = Column(INTEGER(11), nullable=False)
    Number_of_workers = Column(INTEGER(10), nullable=False)
    Id = Column(INTEGER(10), nullable=False)
    Channel_name = Column(CHAR(64), primary_key=True)


class SlaveWorkerInfo(SAFRSBase, Base):
    __tablename__ = "slave_worker_info"

    Id = Column(INTEGER(10), primary_key=True, nullable=False)
    Relay_log_name = Column(TEXT, nullable=False)
    Relay_log_pos = Column(BIGINT(20), nullable=False)
    Master_log_name = Column(TEXT, nullable=False)
    Master_log_pos = Column(BIGINT(20), nullable=False)
    Checkpoint_relay_log_name = Column(TEXT, nullable=False)
    Checkpoint_relay_log_pos = Column(BIGINT(20), nullable=False)
    Checkpoint_master_log_name = Column(TEXT, nullable=False)
    Checkpoint_master_log_pos = Column(BIGINT(20), nullable=False)
    Checkpoint_seqno = Column(INTEGER(10), nullable=False)
    Checkpoint_group_size = Column(INTEGER(10), nullable=False)
    Checkpoint_group_bitmap = Column(LargeBinary, nullable=False)
    Channel_name = Column(CHAR(64), primary_key=True, nullable=False)


t_slow_log = Table(
    "slow_log",
    metadata,
    # Column('start_time', TIMESTAMP(fsp=6), nullable=False, server_default=text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)")),
    #
    # Manual Edit:
    Column("start_time", TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)")),
    Column("user_host", MEDIUMTEXT, nullable=False),
    Column("query_time", TIME(fsp=6), nullable=False),
    Column("lock_time", TIME(fsp=6), nullable=False),
    Column("rows_sent", INTEGER(11), nullable=False),
    Column("rows_examined", INTEGER(11), nullable=False),
    Column("db", String(512), nullable=False),
    Column("last_insert_id", INTEGER(11), nullable=False),
    Column("insert_id", INTEGER(11), nullable=False),
    Column("server_id", INTEGER(10), nullable=False),
    Column("sql_text", MEDIUMBLOB, nullable=False),
    Column("thread_id", BIGINT(21), nullable=False),
)


class TablesPriv(SAFRSBase, Base):
    __tablename__ = "tables_priv"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Db = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Table_name = Column(CHAR(64, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Grantor = Column(CHAR(93, "utf8_bin"), nullable=False, index=True, server_default=text("''"))
    Timestamp = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    Table_priv = Column(SET, nullable=False, server_default=text("''"))
    Column_priv = Column(SET, nullable=False, server_default=text("''"))


class TimeZone(SAFRSBase, Base):
    __tablename__ = "time_zone"

    Time_zone_id = Column(INTEGER(10), primary_key=True)
    Use_leap_seconds = Column(Enum("Y", "N"), nullable=False, server_default=text("'N'"))


class TimeZoneLeapSecond(SAFRSBase, Base):
    __tablename__ = "time_zone_leap_second"

    Transition_time = Column(BIGINT(20), primary_key=True)
    Correction = Column(INTEGER(11), nullable=False)


class TimeZoneName(SAFRSBase, Base):
    __tablename__ = "time_zone_name"

    Name = Column(CHAR(64), primary_key=True)
    Time_zone_id = Column(INTEGER(10), nullable=False)


class TimeZoneTransition(SAFRSBase, Base):
    __tablename__ = "time_zone_transition"

    Time_zone_id = Column(INTEGER(10), primary_key=True, nullable=False)
    Transition_time = Column(BIGINT(20), primary_key=True, nullable=False)
    Transition_type_id = Column(INTEGER(10), nullable=False)


class TimeZoneTransitionType(SAFRSBase, Base):
    __tablename__ = "time_zone_transition_type"

    Time_zone_id = Column(INTEGER(10), primary_key=True, nullable=False)
    Transition_type_id = Column(INTEGER(10), primary_key=True, nullable=False)
    Offset = Column(INTEGER(11), nullable=False, server_default=text("'0'"))
    Is_DST = Column(TINYINT(3), nullable=False, server_default=text("'0'"))
    Abbreviation = Column(CHAR(8), nullable=False, server_default=text("''"))


class User(SAFRSBase, Base):
    __tablename__ = "user"

    Host = Column(CHAR(60, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    User = Column(CHAR(32, "utf8_bin"), primary_key=True, nullable=False, server_default=text("''"))
    Select_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Insert_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Update_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Delete_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Drop_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Reload_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Shutdown_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Process_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    File_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Grant_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    References_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Index_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Alter_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Show_db_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Super_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_tmp_table_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Lock_tables_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Execute_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Repl_slave_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Repl_client_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_view_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Show_view_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_routine_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Alter_routine_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_user_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Event_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Trigger_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    Create_tablespace_priv = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    ssl_type = Column(ENUM("", "ANY", "X509", "SPECIFIED"), nullable=False, server_default=text("''"))
    ssl_cipher = Column(LargeBinary, nullable=False)
    x509_issuer = Column(LargeBinary, nullable=False)
    x509_subject = Column(LargeBinary, nullable=False)
    max_questions = Column(INTEGER(11), nullable=False, server_default=text("'0'"))
    max_updates = Column(INTEGER(11), nullable=False, server_default=text("'0'"))
    max_connections = Column(INTEGER(11), nullable=False, server_default=text("'0'"))
    max_user_connections = Column(INTEGER(11), nullable=False, server_default=text("'0'"))
    plugin = Column(CHAR(64, "utf8_bin"), nullable=False, server_default=text("'mysql_native_password'"))
    authentication_string = Column(Text(collation="utf8_bin"))
    password_expired = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
    password_last_changed = Column(TIMESTAMP)
    password_lifetime = Column(SMALLINT(5))
    account_locked = Column(ENUM("N", "Y"), nullable=False, server_default=text("'N'"))
