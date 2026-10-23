-- Base ficticia para ejecutar SOLO en una base de pruebas vacía.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
CREATE SCHEMA auth;
CREATE SCHEMA storage;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
GRANT USAGE ON SCHEMA auth,storage TO authenticated;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated;
CREATE TABLE auth.users(id uuid PRIMARY KEY);
CREATE TABLE public.perfiles(id uuid PRIMARY KEY, rol text, activo boolean, nombre_completo text);
CREATE TABLE public.categorias(id bigint PRIMARY KEY, nombre text, activa boolean);
CREATE TABLE public.jugadores(id bigint PRIMARY KEY, categoria_id bigint REFERENCES public.categorias(id), institucion text);
CREATE TABLE public.test_vinculos(usuario_id uuid, jugador_id bigint);
GRANT SELECT ON public.perfiles,public.categorias,public.jugadores,public.test_vinculos TO authenticated;
ALTER TABLE public.jugadores ENABLE ROW LEVEL SECURITY;
CREATE POLICY jugadores_simulados ON public.jugadores FOR SELECT TO authenticated USING (
 EXISTS(SELECT 1 FROM public.perfiles p WHERE p.id=auth.uid() AND p.activo AND p.rol IN ('administrador','entrenador','autoridad'))
 OR EXISTS(SELECT 1 FROM public.test_vinculos v WHERE v.usuario_id=auth.uid() AND v.jugador_id=jugadores.id)
);
CREATE TABLE storage.buckets(id text PRIMARY KEY,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
CREATE TABLE storage.objects(id uuid DEFAULT gen_random_uuid(),bucket_id text REFERENCES storage.buckets(id),name text,PRIMARY KEY(bucket_id,name));
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON storage.objects TO authenticated;
-- Simula una política previa demasiado amplia: los límites del nuevo bucket
-- deben seguir protegiendo sus objetos sin editar esta política existente.
CREATE POLICY storage_previo_amplio ON storage.objects FOR ALL TO authenticated USING (true) WITH CHECK (true);
INSERT INTO auth.users SELECT ('00000000-0000-0000-0000-'||lpad(i::text,12,'0'))::uuid FROM generate_series(1,7) i;
INSERT INTO public.perfiles VALUES
 ('00000000-0000-0000-0000-000000000001','administrador',true,'Administración'),
 ('00000000-0000-0000-0000-000000000002','entrenador',true,'Entrenador Surcos'),
 ('00000000-0000-0000-0000-000000000003','entrenador',true,'Otro entrenador'),
 ('00000000-0000-0000-0000-000000000004','autoridad',true,'Autoridad'),
 ('00000000-0000-0000-0000-000000000005','padre',true,'Representante A'),
 ('00000000-0000-0000-0000-000000000006','padre',true,'Representante B'),
 ('00000000-0000-0000-0000-000000000007','entrenador',false,'Inactivo');
INSERT INTO categorias VALUES(10,'Sub 12',true),(20,'Sub 14',true);
INSERT INTO jugadores VALUES(101,10,'Colegio Surcos'),(102,10,'Colegio Surcos'),(103,20,'Colegio Surcos'),(104,10,'Club Juventud');
INSERT INTO test_vinculos VALUES('00000000-0000-0000-0000-000000000005',101),('00000000-0000-0000-0000-000000000006',103);
