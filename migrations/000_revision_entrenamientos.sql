-- Solo lectura: preparar la revisión del esquema y las políticas de producción.
-- No incluye filas personales ni crea/modifica recursos.
SELECT table_schema,table_name,column_name,data_type,udt_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name IN ('perfiles','categorias','jugadores')
ORDER BY table_name,ordinal_position;
SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check
FROM pg_policies
WHERE (schemaname='public' AND tablename IN ('perfiles','categorias','jugadores'))
 OR (schemaname='storage' AND tablename='objects')
ORDER BY schemaname,tablename,policyname;
SELECT n.nspname AS esquema,c.relname AS tabla,c.relrowsecurity AS rls_activo
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('perfiles','categorias','jugadores');
SELECT id,name,public,file_size_limit,allowed_mime_types FROM storage.buckets;
