-- lab5 adds

DROP TABLE IF EXISTS images;

CREATE TABLE images (
       image_id INTEGER PRIMARY KEY AUTOINCREMENT,
       s3key text(1023) UNIQUE NOT NULL,
       linked_message_id INTEGER,
       created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       created_by INTEGER NOT NULL,
       celeb_json text(65535),
       FOREIGN KEY(linked_message_id) REFERENCES messages(messages_id)
         ON UPDATE RESTRICT
         ON DELETE RESTRICT,
       FOREIGN KEY(created_by) REFERENCES api_keys(api_key_id)
         ON UPDATE RESTRICT
         ON DELETE RESTRICT
);

CREATE UNIQUE INDEX s3key_index ON images(s3key);
