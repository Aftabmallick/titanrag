--
-- PostgreSQL database dump
--

\restrict Vxv9tiqKy2y5r7r92LQuwb5ByLWdyLRA4qcpYbOCmNZPHdQk3aPfzjSLNHbfO2z

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

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
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.organizations (id, name, created_at, updated_at, cloud_config) FROM stdin;
cmu5rfvc80001ddf67zs1e9zw	TitanRAG Org	2026-09-17 16:45:01.16	2026-09-17 16:45:01.16	\N
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.projects (id, created_at, name, updated_at, org_id) FROM stdin;
cmu5rhm990006ddf6to1b8x0q	2026-09-17 16:46:22.701	TitanRAG	2026-09-17 16:46:22.701	cmu5rfvc80001ddf67zs1e9zw
\.


--
-- Data for Name: api_keys; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.api_keys (id, created_at, note, public_key, hashed_secret_key, display_secret_key, last_used_at, expires_at, project_id, fast_hashed_secret_key) FROM stdin;
cmu5rjmfz0009ddf6f7zp267o	2026-09-17 16:47:56.255	\N	pk-lf-1960de04-eb39-4c48-9c92-afe1a1b27d1a	$2a$11$lC25bzSi7uK7GtLlT3KSJ.9xnsFAB.hh8Cq9M0P2W5AbBiVT7p0Ee	sk-lf-...4bb4	\N	\N	cmu5rhm990006ddf6to1b8x0q	3ec2d25c6d041f26fe684d62fd18db0d09bc7dd30e2dc4ac44ab1dd39f88f5ea
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, name, email, email_verified, password, image, created_at, updated_at, feature_flags, admin) FROM stdin;
cmu5re72z0000ddf678pogfvl	TitanRAG Admin	admin@titanrag.io	\N	$2a$12$2x2SM7om1Zrx9JSakPawHeY/KwElA3kFZ7atEiLVCSzJtFY2porXu	\N	2026-09-17 16:43:43.067	2026-09-17 16:43:43.067	{}	f
\.


--
-- Data for Name: organization_memberships; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.organization_memberships (id, org_id, user_id, role, created_at, updated_at) FROM stdin;
cmu5rfvc80003ddf6wmm263z0	cmu5rfvc80001ddf67zs1e9zw	cmu5re72z0000ddf678pogfvl	OWNER	2026-09-17 16:45:01.16	2026-09-17 16:45:01.16
\.


--
-- Data for Name: project_memberships; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.project_memberships (project_id, user_id, created_at, updated_at, org_membership_id, role) FROM stdin;
\.


--
-- PostgreSQL database dump complete
--

\unrestrict Vxv9tiqKy2y5r7r92LQuwb5ByLWdyLRA4qcpYbOCmNZPHdQk3aPfzjSLNHbfO2z

