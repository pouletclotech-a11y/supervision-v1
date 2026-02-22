--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alert_rules; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.alert_rules (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    condition_type character varying(50) NOT NULL,
    value character varying(255) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    scope_site_code character varying(50),
    frequency_count integer DEFAULT 1,
    frequency_window integer DEFAULT 0,
    schedule_start character varying(5),
    schedule_end character varying(5),
    email_notify boolean DEFAULT false,
    time_scope character varying(50),
    match_category character varying(50),
    match_keyword character varying(255),
    is_open_only boolean DEFAULT false,
    sliding_window_days integer DEFAULT 0,
    sequence_enabled boolean DEFAULT false,
    seq_a_category character varying(50),
    seq_a_keyword character varying(255),
    seq_b_category character varying(50),
    seq_b_keyword character varying(255),
    seq_max_delay_seconds integer DEFAULT 0,
    seq_lookback_days integer DEFAULT 2,
    logic_enabled boolean DEFAULT false,
    logic_tree jsonb
);


ALTER TABLE public.alert_rules OWNER TO admin;

--
-- Name: alert_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.alert_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.alert_rules_id_seq OWNER TO admin;

--
-- Name: alert_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.alert_rules_id_seq OWNED BY public.alert_rules.id;


--
-- Name: email_bookmarks; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.email_bookmarks (
    id integer NOT NULL,
    folder character varying(100) NOT NULL,
    last_uid bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.email_bookmarks OWNER TO admin;

--
-- Name: email_bookmarks_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.email_bookmarks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.email_bookmarks_id_seq OWNER TO admin;

--
-- Name: email_bookmarks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.email_bookmarks_id_seq OWNED BY public.email_bookmarks.id;


--
-- Name: event_code_catalog; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.event_code_catalog (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    label character varying(255),
    category character varying(50) NOT NULL,
    severity character varying(20) DEFAULT 'info'::character varying,
    alertable_default boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.event_code_catalog OWNER TO admin;

--
-- Name: event_code_catalog_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.event_code_catalog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.event_code_catalog_id_seq OWNER TO admin;

--
-- Name: event_code_catalog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.event_code_catalog_id_seq OWNED BY public.event_code_catalog.id;


--
-- Name: event_rule_hits; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.event_rule_hits (
    id integer NOT NULL,
    event_id bigint NOT NULL,
    rule_id integer NOT NULL,
    rule_name character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.event_rule_hits OWNER TO admin;

--
-- Name: event_rule_hits_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.event_rule_hits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.event_rule_hits_id_seq OWNER TO admin;

--
-- Name: event_rule_hits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.event_rule_hits_id_seq OWNED BY public.event_rule_hits.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.events (
    id bigint NOT NULL,
    "time" timestamp with time zone NOT NULL,
    site_id integer,
    zone_id integer,
    raw_message text,
    raw_code character varying(50),
    normalized_type character varying(100),
    sub_type character varying(50),
    severity character varying(20),
    source_file character varying(255),
    dup_count integer NOT NULL,
    in_maintenance boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    zone_label character varying(255),
    event_metadata json DEFAULT '{}'::json,
    import_id integer,
    site_code character varying(50),
    client_name character varying(255),
    weekday_label character varying(20),
    raw_data text,
    category character varying(50),
    alertable_default boolean DEFAULT false,
    normalized_message text
);


ALTER TABLE public.events OWNER TO admin;

--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.events_id_seq OWNER TO admin;

--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: imports; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.imports (
    id integer NOT NULL,
    filename character varying(255) NOT NULL,
    status character varying(20) NOT NULL,
    events_count integer NOT NULL,
    duplicates_count integer NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    file_hash character varying(64),
    unmatched_count integer DEFAULT 0,
    archive_path text,
    archived_at timestamp with time zone,
    archive_status character varying(20) DEFAULT 'PENDING'::character varying,
    pdf_path text,
    source_message_id character varying(255),
    archived_pdf_hash character varying(64),
    provider_id integer,
    adapter_name character varying(50)
);


ALTER TABLE public.imports OWNER TO admin;

--
-- Name: imports_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.imports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.imports_id_seq OWNER TO admin;

--
-- Name: imports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.imports_id_seq OWNED BY public.imports.id;


--
-- Name: incidents; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.incidents (
    id integer NOT NULL,
    site_code character varying(50) NOT NULL,
    incident_key character varying(128) NOT NULL,
    label text,
    opened_at timestamp with time zone NOT NULL,
    closed_at timestamp with time zone,
    status character varying(20) DEFAULT 'OPEN'::character varying NOT NULL,
    duration_seconds integer,
    open_event_id bigint,
    close_event_id bigint,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.incidents OWNER TO admin;

--
-- Name: incidents_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.incidents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.incidents_id_seq OWNER TO admin;

--
-- Name: incidents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.incidents_id_seq OWNED BY public.incidents.id;


--
-- Name: monitoring_providers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.monitoring_providers (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    label character varying(100) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    ui_color character varying(20)
);


ALTER TABLE public.monitoring_providers OWNER TO admin;

--
-- Name: monitoring_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.monitoring_providers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.monitoring_providers_id_seq OWNER TO admin;

--
-- Name: monitoring_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.monitoring_providers_id_seq OWNED BY public.monitoring_providers.id;


--
-- Name: replay_jobs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.replay_jobs (
    id integer NOT NULL,
    status character varying(20) DEFAULT 'RUNNING'::character varying NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    events_scanned integer DEFAULT 0 NOT NULL,
    alerts_created integer DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.replay_jobs OWNER TO admin;

--
-- Name: replay_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.replay_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.replay_jobs_id_seq OWNER TO admin;

--
-- Name: replay_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.replay_jobs_id_seq OWNED BY public.replay_jobs.id;


--
-- Name: rule_conditions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.rule_conditions (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    label character varying(255),
    type character varying(20) NOT NULL,
    payload jsonb NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rule_conditions_type_check CHECK (((type)::text = ANY ((ARRAY['SIMPLE_V3'::character varying, 'SEQUENCE'::character varying])::text[])))
);


ALTER TABLE public.rule_conditions OWNER TO admin;

--
-- Name: rule_conditions_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.rule_conditions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rule_conditions_id_seq OWNER TO admin;

--
-- Name: rule_conditions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.rule_conditions_id_seq OWNED BY public.rule_conditions.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.settings (
    key character varying(100) NOT NULL,
    value text NOT NULL,
    description character varying(255),
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.settings OWNER TO admin;

--
-- Name: site_connections; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.site_connections (
    id integer NOT NULL,
    provider_id integer NOT NULL,
    code_site character varying(50) NOT NULL,
    client_name character varying(255),
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    first_import_id integer
);


ALTER TABLE public.site_connections OWNER TO admin;

--
-- Name: site_connections_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.site_connections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.site_connections_id_seq OWNER TO admin;

--
-- Name: site_connections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.site_connections_id_seq OWNED BY public.site_connections.id;


--
-- Name: sites; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.sites (
    id integer NOT NULL,
    code_client character varying(50) NOT NULL,
    secondary_code character varying(50),
    name character varying(255) NOT NULL,
    address text,
    contact_info json,
    status character varying(20) NOT NULL,
    tags json,
    config_override json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sites OWNER TO admin;

--
-- Name: sites_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.sites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sites_id_seq OWNER TO admin;

--
-- Name: sites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.sites_id_seq OWNED BY public.sites.id;


--
-- Name: smtp_provider_rules; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.smtp_provider_rules (
    id integer NOT NULL,
    provider_id integer NOT NULL,
    match_type character varying(20) NOT NULL,
    match_value character varying(255) NOT NULL,
    priority integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.smtp_provider_rules OWNER TO admin;

--
-- Name: smtp_provider_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.smtp_provider_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.smtp_provider_rules_id_seq OWNER TO admin;

--
-- Name: smtp_provider_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.smtp_provider_rules_id_seq OWNED BY public.smtp_provider_rules.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(255),
    hashed_password character varying(255) NOT NULL,
    role character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    profile_photo text
);


ALTER TABLE public.users OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: zones; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.zones (
    id integer NOT NULL,
    site_id integer NOT NULL,
    code_zone character varying(50) NOT NULL,
    label character varying(255),
    type character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.zones OWNER TO admin;

--
-- Name: zones_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.zones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.zones_id_seq OWNER TO admin;

--
-- Name: zones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.zones_id_seq OWNED BY public.zones.id;


--
-- Name: alert_rules id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.alert_rules ALTER COLUMN id SET DEFAULT nextval('public.alert_rules_id_seq'::regclass);


--
-- Name: email_bookmarks id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.email_bookmarks ALTER COLUMN id SET DEFAULT nextval('public.email_bookmarks_id_seq'::regclass);


--
-- Name: event_code_catalog id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_code_catalog ALTER COLUMN id SET DEFAULT nextval('public.event_code_catalog_id_seq'::regclass);


--
-- Name: event_rule_hits id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_rule_hits ALTER COLUMN id SET DEFAULT nextval('public.event_rule_hits_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: imports id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.imports ALTER COLUMN id SET DEFAULT nextval('public.imports_id_seq'::regclass);


--
-- Name: incidents id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.incidents ALTER COLUMN id SET DEFAULT nextval('public.incidents_id_seq'::regclass);


--
-- Name: monitoring_providers id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.monitoring_providers ALTER COLUMN id SET DEFAULT nextval('public.monitoring_providers_id_seq'::regclass);


--
-- Name: replay_jobs id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.replay_jobs ALTER COLUMN id SET DEFAULT nextval('public.replay_jobs_id_seq'::regclass);


--
-- Name: rule_conditions id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rule_conditions ALTER COLUMN id SET DEFAULT nextval('public.rule_conditions_id_seq'::regclass);


--
-- Name: site_connections id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.site_connections ALTER COLUMN id SET DEFAULT nextval('public.site_connections_id_seq'::regclass);


--
-- Name: sites id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sites ALTER COLUMN id SET DEFAULT nextval('public.sites_id_seq'::regclass);


--
-- Name: smtp_provider_rules id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.smtp_provider_rules ALTER COLUMN id SET DEFAULT nextval('public.smtp_provider_rules_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: zones id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.zones ALTER COLUMN id SET DEFAULT nextval('public.zones_id_seq'::regclass);


--
-- Name: alert_rules alert_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.alert_rules
    ADD CONSTRAINT alert_rules_pkey PRIMARY KEY (id);


--
-- Name: email_bookmarks email_bookmarks_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.email_bookmarks
    ADD CONSTRAINT email_bookmarks_pkey PRIMARY KEY (id);


--
-- Name: event_code_catalog event_code_catalog_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_code_catalog
    ADD CONSTRAINT event_code_catalog_code_key UNIQUE (code);


--
-- Name: event_code_catalog event_code_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_code_catalog
    ADD CONSTRAINT event_code_catalog_pkey PRIMARY KEY (id);


--
-- Name: event_rule_hits event_rule_hits_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_rule_hits
    ADD CONSTRAINT event_rule_hits_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: imports imports_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.imports
    ADD CONSTRAINT imports_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (id);


--
-- Name: monitoring_providers monitoring_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.monitoring_providers
    ADD CONSTRAINT monitoring_providers_pkey PRIMARY KEY (id);


--
-- Name: replay_jobs replay_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.replay_jobs
    ADD CONSTRAINT replay_jobs_pkey PRIMARY KEY (id);


--
-- Name: rule_conditions rule_conditions_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rule_conditions
    ADD CONSTRAINT rule_conditions_code_key UNIQUE (code);


--
-- Name: rule_conditions rule_conditions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rule_conditions
    ADD CONSTRAINT rule_conditions_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (key);


--
-- Name: site_connections site_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.site_connections
    ADD CONSTRAINT site_connections_pkey PRIMARY KEY (id);


--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);


--
-- Name: smtp_provider_rules smtp_provider_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.smtp_provider_rules
    ADD CONSTRAINT smtp_provider_rules_pkey PRIMARY KEY (id);


--
-- Name: incidents uq_incident_unique; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT uq_incident_unique UNIQUE (site_code, incident_key, opened_at);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: zones zones_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pkey PRIMARY KEY (id);


--
-- Name: idx_email_bookmarks_folder; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_email_bookmarks_folder ON public.email_bookmarks USING btree (folder);


--
-- Name: idx_events_burst_lookup; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_events_burst_lookup ON public.events USING btree (site_id, normalized_type, "time" DESC);


--
-- Name: idx_events_import_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_events_import_id ON public.events USING btree (import_id);


--
-- Name: idx_imports_adapter_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_imports_adapter_name ON public.imports USING btree (adapter_name);


--
-- Name: idx_imports_hash; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_imports_hash ON public.imports USING btree (file_hash);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: ix_alert_rules_category; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_alert_rules_category ON public.alert_rules USING btree (match_category) WHERE (match_category IS NOT NULL);


--
-- Name: ix_alert_rules_seq_enabled; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_alert_rules_seq_enabled ON public.alert_rules USING btree (sequence_enabled) WHERE (sequence_enabled = true);


--
-- Name: ix_email_bookmarks_folder; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_email_bookmarks_folder ON public.email_bookmarks USING btree (folder);


--
-- Name: ix_event_rule_hit_unique; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_event_rule_hit_unique ON public.event_rule_hits USING btree (event_id, rule_id);


--
-- Name: ix_event_rule_hits_event_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_event_rule_hits_event_id ON public.event_rule_hits USING btree (event_id);


--
-- Name: ix_event_rule_hits_rule_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_event_rule_hits_rule_id ON public.event_rule_hits USING btree (rule_id);


--
-- Name: ix_events_normalized_message_btree; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_normalized_message_btree ON public.events USING btree (normalized_message);


--
-- Name: ix_events_normalized_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_normalized_type ON public.events USING btree (normalized_type);


--
-- Name: ix_events_site_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_site_code ON public.events USING btree (site_code);


--
-- Name: ix_events_site_severity_time; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_site_severity_time ON public.events USING btree (site_code, severity, "time");


--
-- Name: ix_events_site_time; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_site_time ON public.events USING btree (site_code, "time");


--
-- Name: ix_events_site_type_time; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_site_type_time ON public.events USING btree (site_code, normalized_type, "time");


--
-- Name: ix_events_time; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_events_time ON public.events USING btree ("time");


--
-- Name: ix_incidents_key_opened; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_incidents_key_opened ON public.incidents USING btree (incident_key, opened_at);


--
-- Name: ix_incidents_site_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_incidents_site_status ON public.incidents USING btree (site_code, status);


--
-- Name: ix_monitoring_providers_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_monitoring_providers_code ON public.monitoring_providers USING btree (code);


--
-- Name: ix_rule_conditions_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_rule_conditions_code ON public.rule_conditions USING btree (code);


--
-- Name: ix_site_connection_unique; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_site_connection_unique ON public.site_connections USING btree (provider_id, code_site);


--
-- Name: ix_site_connections_code_site; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_site_connections_code_site ON public.site_connections USING btree (code_site);


--
-- Name: ix_site_connections_first_seen; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_site_connections_first_seen ON public.site_connections USING btree (first_seen_at);


--
-- Name: ix_site_connections_provider; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_site_connections_provider ON public.site_connections USING btree (provider_id);


--
-- Name: ix_site_connections_provider_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_site_connections_provider_id ON public.site_connections USING btree (provider_id);


--
-- Name: ix_sites_code_client; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_sites_code_client ON public.sites USING btree (code_client);


--
-- Name: ix_smtp_provider_rules_provider_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_smtp_provider_rules_provider_id ON public.smtp_provider_rules USING btree (provider_id);


--
-- Name: ix_smtp_rules_priority; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_smtp_rules_priority ON public.smtp_provider_rules USING btree (priority DESC, match_type);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ux_alert_rules_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ux_alert_rules_name ON public.alert_rules USING btree (name);


--
-- Name: event_rule_hits event_rule_hits_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.event_rule_hits
    ADD CONSTRAINT event_rule_hits_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.alert_rules(id) ON DELETE CASCADE;


--
-- Name: imports imports_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.imports
    ADD CONSTRAINT imports_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.monitoring_providers(id);


--
-- Name: site_connections site_connections_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.site_connections
    ADD CONSTRAINT site_connections_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.monitoring_providers(id) ON DELETE CASCADE;


--
-- Name: smtp_provider_rules smtp_provider_rules_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.smtp_provider_rules
    ADD CONSTRAINT smtp_provider_rules_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.monitoring_providers(id) ON DELETE CASCADE;


--
-- Name: zones zones_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

