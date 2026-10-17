-- PostgreSQL implementation of the logical Data Vault model.
-- Source business IDs must be stable and qualified by source system.
BEGIN;
CREATE SCHEMA cinema_vault;
SET search_path TO cinema_vault;
CREATE TABLE hub_user (
 user_hk CHAR(64) PRIMARY KEY, user_bk TEXT NOT NULL UNIQUE,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL
);
CREATE TABLE hub_film (
 film_hk CHAR(64) PRIMARY KEY, film_bk TEXT NOT NULL UNIQUE,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL
);
CREATE TABLE hub_viewing (
 viewing_hk CHAR(64) PRIMARY KEY, viewing_bk TEXT NOT NULL UNIQUE,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL
);
CREATE TABLE hub_payment (
 payment_hk CHAR(64) PRIMARY KEY, payment_bk TEXT NOT NULL UNIQUE,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL
);
CREATE TABLE link_viewing_user_film (
 viewing_user_film_hk CHAR(64) PRIMARY KEY,
 viewing_hk CHAR(64) NOT NULL REFERENCES hub_viewing,
 user_hk CHAR(64) NOT NULL REFERENCES hub_user,
 film_hk CHAR(64) NOT NULL REFERENCES hub_film,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL,
 UNIQUE(viewing_hk,user_hk,film_hk)
);
CREATE TABLE link_payment_user (
 payment_user_hk CHAR(64) PRIMARY KEY,
 payment_hk CHAR(64) NOT NULL REFERENCES hub_payment,
 user_hk CHAR(64) NOT NULL REFERENCES hub_user,
 load_dts TIMESTAMPTZ NOT NULL, record_source TEXT NOT NULL,
 UNIQUE(payment_hk,user_hk)
);
CREATE TABLE sat_user_profile (
 user_hk CHAR(64) NOT NULL REFERENCES hub_user,
 load_dts TIMESTAMPTZ NOT NULL, hashdiff CHAR(64) NOT NULL,
 record_source TEXT NOT NULL, effective_from TIMESTAMPTZ NOT NULL,
 full_name TEXT, birth_date DATE, email TEXT, phone TEXT,
 registered_at TIMESTAMPTZ, residence_country TEXT,
 PRIMARY KEY(user_hk,load_dts)
);
CREATE TABLE sat_user_subscription (
 user_hk CHAR(64) NOT NULL REFERENCES hub_user,
 load_dts TIMESTAMPTZ NOT NULL, hashdiff CHAR(64) NOT NULL,
 record_source TEXT NOT NULL, effective_from TIMESTAMPTZ NOT NULL,
 subscription_type TEXT,
 PRIMARY KEY(user_hk,load_dts)
);
CREATE TABLE sat_film_details (
 film_hk CHAR(64) NOT NULL REFERENCES hub_film,
 load_dts TIMESTAMPTZ NOT NULL, hashdiff CHAR(64) NOT NULL,
 record_source TEXT NOT NULL, effective_from TIMESTAMPTZ NOT NULL,
 title TEXT, release_date DATE, genres TEXT[], age_restriction TEXT,
 duration_minutes INT, production_countries TEXT[], rating NUMERIC(4,2),
 PRIMARY KEY(film_hk,load_dts)
);
CREATE TABLE sat_viewing_details (
 viewing_hk CHAR(64) NOT NULL REFERENCES hub_viewing,
 load_dts TIMESTAMPTZ NOT NULL, hashdiff CHAR(64) NOT NULL,
 record_source TEXT NOT NULL, effective_from TIMESTAMPTZ NOT NULL,
 started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
 viewing_status TEXT, device_type TEXT,
 PRIMARY KEY(viewing_hk,load_dts)
);
CREATE TABLE sat_payment_details (
 payment_hk CHAR(64) NOT NULL REFERENCES hub_payment,
 load_dts TIMESTAMPTZ NOT NULL, hashdiff CHAR(64) NOT NULL,
 record_source TEXT NOT NULL, effective_from TIMESTAMPTZ NOT NULL,
 paid_at TIMESTAMPTZ, amount NUMERIC(18,2),
 payment_method TEXT, payment_status TEXT, currency CHAR(3),
 PRIMARY KEY(payment_hk,load_dts)
);
COMMIT;
