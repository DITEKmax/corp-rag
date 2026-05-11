-- PostgreSQL bootstrap for the local Phase 1 platform.
-- Java and Python get separate service-owned databases and users.
-- The Langfuse database is platform support for the local container only.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'corp_rag_java') THEN
        CREATE ROLE corp_rag_java LOGIN PASSWORD 'corp_rag_java_password';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'corp_rag_ai') THEN
        CREATE ROLE corp_rag_ai LOGIN PASSWORD 'corp_rag_ai';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'langfuse') THEN
        CREATE ROLE langfuse LOGIN PASSWORD 'langfuse_password';
    END IF;
END
$$;

SELECT 'CREATE DATABASE corp_rag_java OWNER corp_rag_java'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'corp_rag_java')\gexec

SELECT 'CREATE DATABASE corp_rag_ai OWNER corp_rag_ai'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'corp_rag_ai')\gexec

SELECT 'CREATE DATABASE langfuse OWNER langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

\connect corp_rag_java
ALTER SCHEMA public OWNER TO corp_rag_java;
GRANT ALL ON SCHEMA public TO corp_rag_java;

\connect corp_rag_ai
ALTER SCHEMA public OWNER TO corp_rag_ai;
GRANT ALL ON SCHEMA public TO corp_rag_ai;

\connect langfuse
ALTER SCHEMA public OWNER TO langfuse;
GRANT ALL ON SCHEMA public TO langfuse;
