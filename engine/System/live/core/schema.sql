-- The assistant's database. Idempotent: every statement is IF NOT EXISTS, so an
-- existing database keeps its tables (and any extra columns) as they are.

-- Message numbers start at five digits: the thinking and page code recognise a message number in a
-- line of evidence by its length (four to six digits).
CREATE SEQUENCE IF NOT EXISTS seq_message_id START 10001;
CREATE SEQUENCE IF NOT EXISTS seq_attachment_id;
CREATE SEQUENCE IF NOT EXISTS seq_document_id;
CREATE SEQUENCE IF NOT EXISTS seq_page_id;
CREATE SEQUENCE IF NOT EXISTS seq_task_id;
CREATE SEQUENCE IF NOT EXISTS seq_ref_id;
CREATE SEQUENCE IF NOT EXISTS seq_answered_id;
CREATE SEQUENCE IF NOT EXISTS seq_briefing_id;
CREATE SEQUENCE IF NOT EXISTS seq_junk_id;
CREATE SEQUENCE IF NOT EXISTS seq_task_detail_archive_id;
CREATE SEQUENCE IF NOT EXISTS seq_person_id;

-- channel is open: a new kind of connection may add its own.
CREATE TABLE IF NOT EXISTS messages (
  id           BIGINT PRIMARY KEY DEFAULT nextval('seq_message_id'),
  channel      VARCHAR NOT NULL,
  account      VARCHAR NOT NULL,
  provider_id  VARCHAR,
  thread_id    VARCHAR,
  folder       VARCHAR,
  ts           TIMESTAMP NOT NULL,
  direction    VARCHAR NOT NULL CHECK (direction IN ('in','out')),
  from_key     VARCHAR,
  to_keys      VARCHAR,
  person_id    INTEGER,
  subject      VARCHAR,
  body         VARCHAR,
  fingerprint  VARCHAR,
  ingested_at  TIMESTAMP NOT NULL,
  UNIQUE (channel, provider_id)
);

-- message_id is nullable: a parent is preferred, not required.
--
-- THIS IS A STAGING AREA, NOT AN ARCHIVE. A file lives here only until it has
-- been read, judged, and dealt with. state drives that lifecycle:
--   staged     just arrived, not yet read
--   processed  text extracted and classified, awaiting disposition
--   filed      the owner said where it belongs and it was put there; the
--              staged copy is now deletable
--   discarded  spam or noise; deletable
-- Age is NOT the test for deletion; disposition is. An old unprocessed file
-- still needs its moment, and a filed one is deletable the same day.
CREATE TABLE IF NOT EXISTS attachments (
  id                BIGINT PRIMARY KEY DEFAULT nextval('seq_attachment_id'),
  message_id        BIGINT REFERENCES messages(id),
  original_filename VARCHAR,
  saved_filename    VARCHAR NOT NULL,
  saved_path        VARCHAR NOT NULL,
  saved_at          TIMESTAMP,         -- nullable: some older rows never recorded it
  state             VARCHAR NOT NULL DEFAULT 'staged'
                    CHECK (state IN ('staged','processed','filed','discarded')),
  filed_to          VARCHAR,           -- where the owner had it put
  disposed_at       TIMESTAMP          -- when it left the staging area
);

CREATE TABLE IF NOT EXISTS calendar_events (
  event_id    VARCHAR PRIMARY KEY,
  calendar    VARCHAR NOT NULL,
  summary     VARCHAR,
  start_ts    TIMESTAMP,
  end_ts      TIMESTAMP,
  all_day     BOOLEAN,
  location    VARCHAR,
  description VARCHAR,
  updated_at  TIMESTAMP,
  synced_at   TIMESTAMP
);
-- the owner's own answer to an invitation (accepted, declined, tentative, needsAction), as the calendar service gives it:
-- a change between two checks is something he did in his calendar, recorded in the rule book (offpage.py)
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS my_response VARCHAR;

CREATE TABLE IF NOT EXISTS contacts (
  key         VARCHAR PRIMARY KEY,
  person_id   INTEGER NOT NULL,
  name        VARCHAR,
  name_source VARCHAR,
  company     VARCHAR,
  first_seen  TIMESTAMP,
  last_seen   TIMESTAMP,
  sent_count  INTEGER DEFAULT 0,
  received_count INTEGER DEFAULT 0,
  sent_90     INTEGER DEFAULT 0,
  received_90 INTEGER DEFAULT 0,
  weeks_written INTEGER DEFAULT 0,
  strength    DOUBLE DEFAULT 0,
  counted_at  TIMESTAMP,
  notes       VARCHAR,
  updated_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id              BIGINT PRIMARY KEY DEFAULT nextval('seq_document_id'),
  message_id      BIGINT REFERENCES messages(id),
  attachment_id   BIGINT REFERENCES attachments(id),
  doc_type        VARCHAR,
  doc_date        DATE,
  created_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
  id           BIGINT PRIMARY KEY DEFAULT nextval('seq_page_id'),
  document_id  BIGINT NOT NULL REFERENCES documents(id),
  page_no      INTEGER NOT NULL,
  method       VARCHAR,
  text         VARCHAR,
  extracted_at TIMESTAMP,
  UNIQUE (document_id, page_no)
);

CREATE TABLE IF NOT EXISTS tasks (
  id              BIGINT PRIMARY KEY DEFAULT nextval('seq_task_id'),
  item_key        VARCHAR NOT NULL UNIQUE,
  kind            VARCHAR NOT NULL DEFAULT 'task',
  area            VARCHAR NOT NULL,
  title           VARCHAR NOT NULL,
  detail          VARCHAR,
  person_id       INTEGER,
  status          VARCHAR NOT NULL,
  due_date        DATE,
  checkback_date  DATE,
  first_seen      DATE,
  last_seen       DATE,
  resolved_reason VARCHAR,
  created_at      TIMESTAMP NOT NULL,
  updated_at      TIMESTAMP NOT NULL,
  urgency         VARCHAR DEFAULT 'normal',
  urgency_reason  VARCHAR
);

CREATE TABLE IF NOT EXISTS task_refs (
  id         BIGINT PRIMARY KEY DEFAULT nextval('seq_ref_id'),
  task_id    BIGINT NOT NULL REFERENCES tasks(id),
  kind       VARCHAR NOT NULL,
  ref_type   VARCHAR NOT NULL,
  value      VARCHAR NOT NULL,
  value_norm VARCHAR,
  role       VARCHAR,
  noted_at   TIMESTAMP
);

-- The judge compacts a task detail that has grown past its useful length. The
-- text it replaced lands here first, so a rewrite is a compression and never a
-- loss: the full original is always recoverable by task_id.
CREATE TABLE IF NOT EXISTS task_detail_archive (
  id          BIGINT PRIMARY KEY DEFAULT nextval('seq_task_detail_archive_id'),
  task_id     BIGINT NOT NULL REFERENCES tasks(id),
  archived_at TIMESTAMP NOT NULL,
  detail      VARCHAR,
  run_id      VARCHAR
);

-- Rules are not in the database: they live in Resources\Rules, one
-- document per subject. See rules.py beside this file.

CREATE TABLE IF NOT EXISTS answered (
  id          BIGINT PRIMARY KEY DEFAULT nextval('seq_answered_id'),
  domain      VARCHAR NOT NULL,
  key         VARCHAR NOT NULL,
  verdict     VARCHAR NOT NULL,
  source      VARCHAR NOT NULL,
  answered_at TIMESTAMP NOT NULL,
  UNIQUE (domain, key)
);

-- The judge's word on whether a rule decided the message (judgment_commit.py): covered false means its verdict is its
-- own best guess (the reason); NULL, from every other writer and from a verdict that did not say, counts as covered.
-- leaned_on is the rule id or the few words the call leaned on.
ALTER TABLE answered ADD COLUMN IF NOT EXISTS covered BOOLEAN;
ALTER TABLE answered ADD COLUMN IF NOT EXISTS leaned_on VARCHAR;

CREATE TABLE IF NOT EXISTS runs (
  run_id      VARCHAR PRIMARY KEY,
  started_at  TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  outcome     VARCHAR NOT NULL,
  note        VARCHAR
);

CREATE TABLE IF NOT EXISTS run_steps (
  run_id    VARCHAR NOT NULL REFERENCES runs(run_id),
  seq       INTEGER NOT NULL,
  step      VARCHAR NOT NULL,
  status    VARCHAR NOT NULL,
  exit_code INTEGER,
  secs      DOUBLE,
  at_ts     TIMESTAMP,
  output    VARCHAR,
  PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS source_status (
  run_id     VARCHAR NOT NULL REFERENCES runs(run_id),
  source     VARCHAR NOT NULL,
  status     VARCHAR NOT NULL,
  detail     VARCHAR,
  updated_at TIMESTAMP,
  PRIMARY KEY (run_id, source)
);

CREATE TABLE IF NOT EXISTS watermarks (
  source     VARCHAR PRIMARY KEY,
  position   VARCHAR NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS junk_deleted (
  id           BIGINT PRIMARY KEY DEFAULT nextval('seq_junk_id'),
  channel      VARCHAR,
  account      VARCHAR,
  provider_id  VARCHAR,
  from_address VARCHAR,
  subject      VARCHAR,
  msg_ts       TIMESTAMP,
  reason       VARCHAR NOT NULL,
  action       VARCHAR NOT NULL,
  note         VARCHAR,
  deleted_at   TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS briefings (
  id            BIGINT PRIMARY KEY DEFAULT nextval('seq_briefing_id'),
  briefing_date DATE NOT NULL,
  file          VARCHAR NOT NULL,
  run_id        VARCHAR REFERENCES runs(run_id),
  created_at    TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS briefing_items (
  briefing_id BIGINT NOT NULL REFERENCES briefings(id),
  number      VARCHAR NOT NULL,
  item_key    VARCHAR NOT NULL,
  section     VARCHAR,
  PRIMARY KEY (briefing_id, number)
);

CREATE TABLE IF NOT EXISTS unsubscribes (
  from_key    VARCHAR PRIMARY KEY,
  sender_name VARCHAR,
  account     VARCHAR,
  method      VARCHAR,
  target      VARCHAR,
  msg_count   INTEGER,
  last_ts     TIMESTAMP,
  noise       BOOLEAN,
  example_id  BIGINT,
  verdict     VARCHAR,
  verdict_at  TIMESTAMP,
  done_at     TIMESTAMP,
  done_note   VARCHAR,
  found_at    TIMESTAMP
);

-- What the mail service says about a stored email: whether it is unread, in the inbox or in the trash, its labels,
-- and the headers a reply or forward needs. One row per stored email; written when it is read, refreshed by each
-- pass for recent mail, and changed when the owner presses Archive, Delete, Label or Mark read on the page.
-- A NULL means the service has not said yet.
CREATE TABLE IF NOT EXISTS mail_state (
  message_id   BIGINT PRIMARY KEY,
  account      VARCHAR,
  provider_id  VARCHAR,
  unread       BOOLEAN,
  inbox        BOOLEAN,
  trashed      BOOLEAN,
  labels       VARCHAR,             -- JSON list of label or category names
  cc           VARCHAR,             -- comma list of the copy addresses
  from_name    VARCHAR,
  header_id    VARCHAR,             -- the email's own Message-ID header
  refs         VARCHAR,             -- its References header
  updated_at   TIMESTAMP
);

-- When the stored email's state was last read from the mail service (NULL: not yet; the backfill reads those a portion at a time).
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP;
-- Set when the email was stored under an id the mail service does not know (an earlier import's) and the service could not
-- find it by its Message-ID: the backfill does not ask for it again.
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS unmatched_at TIMESTAMP;
-- The full history reload (Settings, Tools): when the service last listed the email in a reload, and, once a reload has
-- finished, when a stored email was found to have no copy at the service any more (kept as history).
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS reload_seen TIMESTAMP;
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS server_gone TIMESTAMP;

-- Each email's own HTML as it was sent (the Mail page shows it; everything the assistant reads uses messages.body, its plain
-- text). cids: JSON {content id: "att:<attachment id>"}, the email's pictures shown in its body, kept as its attachments.
CREATE TABLE IF NOT EXISTS mail_html (
  message_id BIGINT PRIMARY KEY,
  html       VARCHAR,
  cids       VARCHAR,
  stored_at  TIMESTAMP
);

-- What each email's List-Unsubscribe header said (kept by the first lookup) and whether the Unsubscribe press has been done.
CREATE TABLE IF NOT EXISTS mail_unsub (
  message_id BIGINT PRIMARY KEY,
  account    VARCHAR,
  list_value VARCHAR,
  post_value VARCHAR,
  checked_at TIMESTAMP,
  done_at    TIMESTAMP,
  how        VARCHAR
);

-- Where each mailbox's incremental sync stands: Gmail scope 'history' (the historyId); Microsoft scope 'delta:<folder id>'
-- (a JSON {"next": url} while its first round is still being read, {"delta": url} once it is current); 'immutable' (id move done).
CREATE TABLE IF NOT EXISTS mail_cursors (
  account    VARCHAR NOT NULL,
  scope      VARCHAR NOT NULL,
  cursor     VARCHAR,
  updated_at TIMESTAMP,
  PRIMARY KEY (account, scope)
);

-- Each mailbox's folder tree (Microsoft) or label list (Gmail, system labels kept). path reads like "Inbox/Suppliers".
-- kind: inbox, sent, trash, spam, drafts, archive, outbox, folder or label. unread and total are the service's own counts.
CREATE TABLE IF NOT EXISTS mail_folders (
  account    VARCHAR NOT NULL,
  folder_id  VARCHAR NOT NULL,
  path       VARCHAR,
  parent_id  VARCHAR,
  kind       VARCHAR,
  unread     INTEGER,
  total      INTEGER,
  updated_at TIMESTAMP,
  PRIMARY KEY (account, folder_id)
);

-- Which folder (Microsoft: one) or labels (Gmail: several) each stored email is in.
CREATE TABLE IF NOT EXISTS mail_folder_members (
  message_id BIGINT NOT NULL,
  account    VARCHAR NOT NULL,
  folder_id  VARCHAR NOT NULL,
  PRIMARY KEY (message_id, folder_id)
);

-- Star (Gmail STARRED, Microsoft flag), a snooze time kept here only (the email comes back to the inbox then), and the
-- conversation a threader (References / In-Reply-To) gave an email the service gave no conversation id.
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS starred BOOLEAN;
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS snooze_until TIMESTAMP;
ALTER TABLE mail_state ADD COLUMN IF NOT EXISTS conv VARCHAR;
