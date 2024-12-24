-- lab4 database server schema

DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS messages;

CREATE TABLE api_keys (
       api_key_id INTEGER PRIMARY KEY AUTOINCREMENT,
       api_key text(255) UNIQUE NOT NULL,
       api_secret_key_hash text(255) NOT NULL,
       created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       last_used TIMESTAMP,
       remaining INTEGER DEFAULT 1000
);

CREATE UNIQUE INDEX api_key_index ON api_keys(api_key);

CREATE TABLE messages (
       messages_id INTEGER PRIMARY KEY AUTOINCREMENT,
       message text(4096),
       created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       created_by INTEGER NOT NULL,
       FOREIGN KEY(created_by) REFERENCES api_keys(api_key_id)
         ON UPDATE RESTRICT
         ON DELETE RESTRICT
);


-- Delete this for lab4:

CREATE TABLE images (
       image_id INTEGER PRIMARY KEY AUTOINCREMENT,
       s3key text(1023) UNIQUE NOT NULL,
       linked_messages INTEGER,
       created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       created_by INTEGER NOT NULL,
       celeb text(65535),
       FOREIGN KEY(linked_messages) REFERENCES messages(messages_id)
         ON UPDATE RESTRICT
         ON DELETE RESTRICT,
       FOREIGN KEY(created_by) REFERENCES api_keys(api_key_id)
         ON UPDATE RESTRICT
         ON DELETE RESTRICT
);

CREATE UNIQUE INDEX s3key_index ON images(s3key);
