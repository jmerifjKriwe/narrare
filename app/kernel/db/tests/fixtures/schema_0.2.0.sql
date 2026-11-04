--
-- PostgreSQL database dump
--

-- Dumped from database version 17.10 (Debian 17.10-1.pgdg12+1)
-- Dumped by pg_dump version 17.10 (Debian 17.10-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chapters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chapters (
    id uuid NOT NULL,
    novel_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    "position" integer NOT NULL,
    body text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunks (
    id uuid NOT NULL,
    document_id uuid NOT NULL,
    "position" integer NOT NULL,
    text text NOT NULL,
    embedding public.vector NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: consistency_findings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consistency_findings (
    id uuid NOT NULL,
    novel_id uuid NOT NULL,
    summary character varying(200) NOT NULL,
    detail text,
    status character varying(16) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid NOT NULL,
    title character varying(200) NOT NULL,
    embedding_width integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entities (
    id uuid NOT NULL,
    novel_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    type character varying(40) NOT NULL,
    content text NOT NULL,
    aliases jsonb NOT NULL,
    tags jsonb NOT NULL,
    search_text text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: entity_relations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_relations (
    id uuid NOT NULL,
    from_entity_id uuid NOT NULL,
    to_entity_id uuid NOT NULL,
    relation_type character varying(80) NOT NULL,
    note text,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: entity_suggestions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_suggestions (
    id uuid NOT NULL,
    novel_id uuid NOT NULL,
    chapter_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    type character varying(40) NOT NULL,
    description text,
    relations jsonb NOT NULL,
    status character varying(16) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs (
    id uuid NOT NULL,
    kind character varying(100) NOT NULL,
    status character varying(16) NOT NULL,
    progress integer,
    error text,
    retry_count integer NOT NULL,
    payload json NOT NULL,
    result json,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: llm_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_calls (
    id uuid NOT NULL,
    novel_id uuid,
    profile_id uuid,
    task_key character varying(100) NOT NULL,
    prompt_key character varying(100),
    provider_kind character varying(40) NOT NULL,
    model character varying(200) NOT NULL,
    input_tokens integer,
    output_tokens integer,
    cost_usd double precision,
    latency_ms integer NOT NULL,
    status character varying(16) NOT NULL,
    error text,
    prompt_text text NOT NULL,
    response_text text NOT NULL,
    truncated boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: novels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.novels (
    id uuid NOT NULL,
    title character varying(200) NOT NULL,
    genre character varying(80),
    blurb text,
    author character varying(200),
    language character varying(16),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_templates (
    id uuid NOT NULL,
    novel_id uuid,
    prompt_key character varying(80) NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: provider_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.provider_profiles (
    id uuid NOT NULL,
    name character varying(120) NOT NULL,
    kind character varying(40) NOT NULL,
    base_url character varying(500),
    model character varying(200),
    api_key text NOT NULL,
    api_key_hint character varying(8),
    is_default boolean NOT NULL,
    context_window integer,
    max_output_tokens integer,
    temperature double precision,
    request_timeout double precision,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: task_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_assignments (
    id uuid NOT NULL,
    task_key character varying(100) NOT NULL,
    profile_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(320),
    locale character varying(8),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: chapters pk_chapters; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chapters
    ADD CONSTRAINT pk_chapters PRIMARY KEY (id);


--
-- Name: chunks pk_chunks; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT pk_chunks PRIMARY KEY (id);


--
-- Name: consistency_findings pk_consistency_findings; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consistency_findings
    ADD CONSTRAINT pk_consistency_findings PRIMARY KEY (id);


--
-- Name: documents pk_documents; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT pk_documents PRIMARY KEY (id);


--
-- Name: entities pk_entities; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT pk_entities PRIMARY KEY (id);


--
-- Name: entity_relations pk_entity_relations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relations
    ADD CONSTRAINT pk_entity_relations PRIMARY KEY (id);


--
-- Name: entity_suggestions pk_entity_suggestions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_suggestions
    ADD CONSTRAINT pk_entity_suggestions PRIMARY KEY (id);


--
-- Name: jobs pk_jobs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT pk_jobs PRIMARY KEY (id);


--
-- Name: llm_calls pk_llm_calls; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT pk_llm_calls PRIMARY KEY (id);


--
-- Name: novels pk_novels; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.novels
    ADD CONSTRAINT pk_novels PRIMARY KEY (id);


--
-- Name: prompt_templates pk_prompt_templates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT pk_prompt_templates PRIMARY KEY (id);


--
-- Name: provider_profiles pk_provider_profiles; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_profiles
    ADD CONSTRAINT pk_provider_profiles PRIMARY KEY (id);


--
-- Name: task_assignments pk_task_assignments; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignments
    ADD CONSTRAINT pk_task_assignments PRIMARY KEY (id);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: entity_relations uq_entity_relations_edge; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relations
    ADD CONSTRAINT uq_entity_relations_edge UNIQUE (user_id, from_entity_id, to_entity_id, relation_type);


--
-- Name: prompt_templates uq_prompt_templates_novel_scope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT uq_prompt_templates_novel_scope UNIQUE (user_id, novel_id, prompt_key);


--
-- Name: task_assignments uq_task_assignments_user_task; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignments
    ADD CONSTRAINT uq_task_assignments_user_task UNIQUE (user_id, task_key);


--
-- Name: users uq_users_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_email UNIQUE (email);


--
-- Name: ix_chapters_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chapters_user_id ON public.chapters USING btree (user_id);


--
-- Name: ix_chunks_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunks_user_id ON public.chunks USING btree (user_id);


--
-- Name: ix_consistency_findings_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consistency_findings_user_id ON public.consistency_findings USING btree (user_id);


--
-- Name: ix_documents_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_user_id ON public.documents USING btree (user_id);


--
-- Name: ix_entities_search_text; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_search_text ON public.entities USING gin (search_text public.gin_trgm_ops);


--
-- Name: ix_entities_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_user_id ON public.entities USING btree (user_id);


--
-- Name: ix_entity_relations_from_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entity_relations_from_entity_id ON public.entity_relations USING btree (from_entity_id);


--
-- Name: ix_entity_relations_to_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entity_relations_to_entity_id ON public.entity_relations USING btree (to_entity_id);


--
-- Name: ix_entity_relations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entity_relations_user_id ON public.entity_relations USING btree (user_id);


--
-- Name: ix_entity_suggestions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entity_suggestions_user_id ON public.entity_suggestions USING btree (user_id);


--
-- Name: ix_jobs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_user_id ON public.jobs USING btree (user_id);


--
-- Name: ix_llm_calls_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_llm_calls_user_id ON public.llm_calls USING btree (user_id);


--
-- Name: ix_novels_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_novels_user_id ON public.novels USING btree (user_id);


--
-- Name: ix_prompt_templates_novel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_templates_novel_id ON public.prompt_templates USING btree (novel_id);


--
-- Name: ix_prompt_templates_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_templates_user_id ON public.prompt_templates USING btree (user_id);


--
-- Name: ix_provider_profiles_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_provider_profiles_user_id ON public.provider_profiles USING btree (user_id);


--
-- Name: ix_task_assignments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_task_assignments_user_id ON public.task_assignments USING btree (user_id);


--
-- Name: uq_prompt_templates_one_global_per_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_prompt_templates_one_global_per_key ON public.prompt_templates USING btree (user_id, prompt_key) WHERE (novel_id IS NULL);


--
-- Name: uq_provider_profiles_one_default_per_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_provider_profiles_one_default_per_user ON public.provider_profiles USING btree (user_id) WHERE is_default;


--
-- Name: chapters fk_chapters_novel_id_novels; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chapters
    ADD CONSTRAINT fk_chapters_novel_id_novels FOREIGN KEY (novel_id) REFERENCES public.novels(id) ON DELETE CASCADE;


--
-- Name: chapters fk_chapters_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chapters
    ADD CONSTRAINT fk_chapters_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chunks fk_chunks_document_id_documents; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT fk_chunks_document_id_documents FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: chunks fk_chunks_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT fk_chunks_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: consistency_findings fk_consistency_findings_novel_id_novels; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consistency_findings
    ADD CONSTRAINT fk_consistency_findings_novel_id_novels FOREIGN KEY (novel_id) REFERENCES public.novels(id) ON DELETE CASCADE;


--
-- Name: consistency_findings fk_consistency_findings_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consistency_findings
    ADD CONSTRAINT fk_consistency_findings_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents fk_documents_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: entities fk_entities_novel_id_novels; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT fk_entities_novel_id_novels FOREIGN KEY (novel_id) REFERENCES public.novels(id) ON DELETE CASCADE;


--
-- Name: entities fk_entities_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT fk_entities_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: entity_relations fk_entity_relations_from_entity_id_entities; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relations
    ADD CONSTRAINT fk_entity_relations_from_entity_id_entities FOREIGN KEY (from_entity_id) REFERENCES public.entities(id) ON DELETE CASCADE;


--
-- Name: entity_relations fk_entity_relations_to_entity_id_entities; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relations
    ADD CONSTRAINT fk_entity_relations_to_entity_id_entities FOREIGN KEY (to_entity_id) REFERENCES public.entities(id) ON DELETE CASCADE;


--
-- Name: entity_relations fk_entity_relations_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relations
    ADD CONSTRAINT fk_entity_relations_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: entity_suggestions fk_entity_suggestions_chapter_id_chapters; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_suggestions
    ADD CONSTRAINT fk_entity_suggestions_chapter_id_chapters FOREIGN KEY (chapter_id) REFERENCES public.chapters(id) ON DELETE CASCADE;


--
-- Name: entity_suggestions fk_entity_suggestions_novel_id_novels; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_suggestions
    ADD CONSTRAINT fk_entity_suggestions_novel_id_novels FOREIGN KEY (novel_id) REFERENCES public.novels(id) ON DELETE CASCADE;


--
-- Name: entity_suggestions fk_entity_suggestions_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_suggestions
    ADD CONSTRAINT fk_entity_suggestions_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: jobs fk_jobs_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT fk_jobs_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: llm_calls fk_llm_calls_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT fk_llm_calls_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: novels fk_novels_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.novels
    ADD CONSTRAINT fk_novels_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: prompt_templates fk_prompt_templates_novel_id_novels; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT fk_prompt_templates_novel_id_novels FOREIGN KEY (novel_id) REFERENCES public.novels(id) ON DELETE CASCADE;


--
-- Name: prompt_templates fk_prompt_templates_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT fk_prompt_templates_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: provider_profiles fk_provider_profiles_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_profiles
    ADD CONSTRAINT fk_provider_profiles_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: task_assignments fk_task_assignments_profile_id_provider_profiles; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignments
    ADD CONSTRAINT fk_task_assignments_profile_id_provider_profiles FOREIGN KEY (profile_id) REFERENCES public.provider_profiles(id) ON DELETE CASCADE;


--
-- Name: task_assignments fk_task_assignments_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignments
    ADD CONSTRAINT fk_task_assignments_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

