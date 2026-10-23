-- PROPUESTA para revisión. No ejecutar automáticamente en producción.
-- Conserva las tablas y políticas existentes; crea recursos propios del módulo.
BEGIN;
CREATE SCHEMA IF NOT EXISTS ent_privado;
REVOKE ALL ON SCHEMA ent_privado FROM PUBLIC;
GRANT USAGE ON SCHEMA ent_privado TO authenticated;

CREATE FUNCTION ent_privado.rol() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT p.rol::text FROM public.perfiles p
  WHERE p.id::text = auth.uid()::text AND p.activo = true
$$;
REVOKE ALL ON FUNCTION ent_privado.rol() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ent_privado.rol() TO authenticated;

-- Se toman los tipos reales de las claves existentes, sin asumir bigint o UUID.
DO $migracion$
DECLARE tipo_categoria text; tipo_jugador text;
BEGIN
  SELECT format_type(atttypid, atttypmod) INTO STRICT tipo_categoria
    FROM pg_attribute WHERE attrelid='public.categorias'::regclass AND attname='id' AND NOT attisdropped;
  SELECT format_type(atttypid, atttypmod) INTO STRICT tipo_jugador
    FROM pg_attribute WHERE attrelid='public.jugadores'::regclass AND attname='id' AND NOT attisdropped;
  EXECUTE format($ddl$
    CREATE TABLE public.ent_grupos (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      institucion text NOT NULL CHECK (institucion IN ('Club Juventud', 'Colegio Surcos')),
      categoria_id %s NOT NULL REFERENCES public.categorias(id),
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(institucion, categoria_id)
    )$ddl$, tipo_categoria);
  EXECUTE format($ddl$
    CREATE TABLE public.ent_asistencias (
      sesion_id uuid NOT NULL,
      jugador_id %s NOT NULL REFERENCES public.jugadores(id),
      estado text NOT NULL CHECK (estado IN ('presente','ausente','justificado','sin_registrar')),
      updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(sesion_id,jugador_id)
    )$ddl$, tipo_jugador);
END $migracion$;

CREATE TABLE public.ent_asignaciones (
  grupo_id uuid NOT NULL REFERENCES public.ent_grupos(id),
  usuario_id uuid NOT NULL REFERENCES auth.users(id),
  PRIMARY KEY(grupo_id,usuario_id)
);
CREATE TABLE public.ent_sesiones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  grupo_id uuid NOT NULL REFERENCES public.ent_grupos(id),
  creado_por uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id),
  autor_nombre text NOT NULL DEFAULT '',
  fecha date NOT NULL,
  titulo text NOT NULL CHECK (length(btrim(titulo)) BETWEEN 1 AND 160),
  objetivos text NOT NULL CHECK (length(btrim(objetivos)) BETWEEN 1 AND 4000),
  contenido text NOT NULL CHECK (length(btrim(contenido)) BETWEEN 1 AND 20000),
  estado text NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador','publicada')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.ent_asistencias ADD FOREIGN KEY(sesion_id) REFERENCES public.ent_sesiones(id);
CREATE TABLE public.ent_archivos (
  id uuid PRIMARY KEY,
  sesion_id uuid NOT NULL REFERENCES public.ent_sesiones(id),
  tipo text NOT NULL CHECK (tipo IN ('plan','foto')),
  ruta text NOT NULL UNIQUE,
  nombre text NOT NULL CHECK (length(nombre) BETWEEN 1 AND 180),
  mime text NOT NULL,
  tamano bigint NOT NULL CHECK (tamano BETWEEN 1 AND 10485760),
  confirmado boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((tipo='plan' AND mime='application/pdf') OR (tipo='foto' AND mime IN ('image/png','image/jpeg')))
);
CREATE UNIQUE INDEX ent_un_plan ON public.ent_archivos(sesion_id) WHERE tipo='plan';
CREATE INDEX ent_sesiones_grupo_fecha ON public.ent_sesiones(grupo_id,fecha DESC,id);
CREATE INDEX ent_archivos_sesion ON public.ent_archivos(sesion_id);
CREATE INDEX ent_asignaciones_usuario ON public.ent_asignaciones(usuario_id);
CREATE INDEX ent_asistencias_jugador ON public.ent_asistencias(jugador_id);

CREATE FUNCTION ent_privado.entrenador_grupo(p_grupo uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT ent_privado.rol()='entrenador' AND EXISTS (
   SELECT 1 FROM public.ent_asignaciones a WHERE a.grupo_id=p_grupo AND a.usuario_id=auth.uid()
 )
$$;
CREATE FUNCTION ent_privado.editar_sesion(p_sesion uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT EXISTS (SELECT 1 FROM public.ent_sesiones s WHERE s.id=p_sesion AND (
   ent_privado.rol()='administrador' OR (s.creado_por=auth.uid() AND ent_privado.entrenador_grupo(s.grupo_id))
 ))
$$;
REVOKE ALL ON FUNCTION ent_privado.entrenador_grupo(uuid), ent_privado.editar_sesion(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ent_privado.entrenador_grupo(uuid), ent_privado.editar_sesion(uuid) TO authenticated;

ALTER TABLE public.ent_grupos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ent_asignaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ent_sesiones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ent_archivos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ent_asistencias ENABLE ROW LEVEL SECURITY;

CREATE POLICY ent_grupos_lectura ON public.ent_grupos FOR SELECT TO authenticated USING (
  ent_privado.rol()='administrador' OR ent_privado.entrenador_grupo(id)
  OR (ent_privado.rol()='autoridad' AND institucion='Colegio Surcos')
  OR (ent_privado.rol()='padre' AND EXISTS (
    -- Esta subconsulta se evalúa con las RLS existentes de jugadores, sin SECURITY DEFINER.
    SELECT 1 FROM public.jugadores j WHERE j.categoria_id=ent_grupos.categoria_id
    AND coalesce(j.institucion,'Club Juventud')=ent_grupos.institucion
  ))
);
CREATE POLICY ent_grupos_crear ON public.ent_grupos FOR INSERT TO authenticated
  WITH CHECK (ent_privado.rol()='administrador');
CREATE POLICY ent_asignaciones_lectura ON public.ent_asignaciones FOR SELECT TO authenticated
  USING (ent_privado.rol()='administrador' OR usuario_id=auth.uid());
CREATE POLICY ent_asignaciones_crear ON public.ent_asignaciones FOR INSERT TO authenticated
  WITH CHECK (ent_privado.rol()='administrador' AND EXISTS (
    SELECT 1 FROM public.perfiles p WHERE p.id::text=usuario_id::text AND p.rol='entrenador' AND p.activo=true
  ));
CREATE POLICY ent_asignaciones_quitar ON public.ent_asignaciones FOR DELETE TO authenticated
  USING (ent_privado.rol()='administrador');
CREATE POLICY ent_sesiones_lectura ON public.ent_sesiones FOR SELECT TO authenticated USING (
  ent_privado.rol()='administrador' OR ent_privado.editar_sesion(id)
  OR (estado='publicada' AND EXISTS (SELECT 1 FROM public.ent_grupos g WHERE g.id=grupo_id))
);
CREATE POLICY ent_sesiones_crear ON public.ent_sesiones FOR INSERT TO authenticated WITH CHECK (
  creado_por=auth.uid() AND (ent_privado.rol()='administrador' OR ent_privado.entrenador_grupo(grupo_id))
);
CREATE POLICY ent_sesiones_editar ON public.ent_sesiones FOR UPDATE TO authenticated
  USING (ent_privado.editar_sesion(id)) WITH CHECK (ent_privado.editar_sesion(id));
CREATE POLICY ent_archivos_lectura ON public.ent_archivos FOR SELECT TO authenticated USING (
  ent_privado.editar_sesion(sesion_id) OR (confirmado AND EXISTS (
    SELECT 1 FROM public.ent_sesiones s WHERE s.id=sesion_id
  ))
);
CREATE POLICY ent_archivos_crear ON public.ent_archivos FOR INSERT TO authenticated
  WITH CHECK (ent_privado.editar_sesion(sesion_id) AND NOT confirmado);
CREATE POLICY ent_archivos_quitar_pendiente ON public.ent_archivos FOR DELETE TO authenticated
  USING (NOT confirmado AND ent_privado.editar_sesion(sesion_id));
CREATE POLICY ent_asistencias_lectura ON public.ent_asistencias FOR SELECT TO authenticated USING (
  EXISTS (SELECT 1 FROM public.ent_sesiones s WHERE s.id=sesion_id)
  AND (ent_privado.rol() IN ('administrador','entrenador','autoridad') OR (
    ent_privado.rol()='padre' AND EXISTS (SELECT 1 FROM public.jugadores j WHERE j.id=jugador_id)
  ))
);
CREATE POLICY ent_asistencias_crear ON public.ent_asistencias FOR INSERT TO authenticated
  WITH CHECK (ent_privado.editar_sesion(sesion_id));
CREATE POLICY ent_asistencias_editar ON public.ent_asistencias FOR UPDATE TO authenticated
  USING (ent_privado.editar_sesion(sesion_id)) WITH CHECK (ent_privado.editar_sesion(sesion_id));

CREATE FUNCTION ent_privado.validar_sesion() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
 IF TG_OP='INSERT' THEN
   IF NEW.estado <> 'borrador' OR NEW.creado_por IS DISTINCT FROM auth.uid() THEN
     RAISE EXCEPTION 'Una sesión nueva debe ser un borrador propio';
   END IF;
   SELECT coalesce(p.nombre_completo,'Equipo técnico') INTO NEW.autor_nombre FROM public.perfiles p WHERE p.id::text=auth.uid()::text;
 ELSE
   IF NEW.id<>OLD.id OR NEW.grupo_id<>OLD.grupo_id OR NEW.creado_por<>OLD.creado_por OR NEW.autor_nombre<>OLD.autor_nombre OR NEW.created_at<>OLD.created_at THEN
     RAISE EXCEPTION 'No se puede cambiar la identidad de la sesión';
   END IF;
 END IF;
 IF NEW.estado='publicada' AND EXISTS (SELECT 1 FROM public.ent_archivos a WHERE a.sesion_id=NEW.id AND NOT a.confirmado) THEN
   RAISE EXCEPTION 'Hay archivos pendientes; completa o retira esas cargas antes de publicar';
 END IF;
 NEW.updated_at=now(); RETURN NEW;
END $$;
CREATE TRIGGER ent_validar_sesion BEFORE INSERT OR UPDATE ON public.ent_sesiones
  FOR EACH ROW EXECUTE FUNCTION ent_privado.validar_sesion();

CREATE FUNCTION ent_privado.validar_archivo() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
 IF NEW.ruta NOT IN (NEW.sesion_id::text||'/'||NEW.id::text||'.pdf', NEW.sesion_id::text||'/'||NEW.id::text||'.png', NEW.sesion_id::text||'/'||NEW.id::text||'.jpg')
 OR split_part(NEW.ruta,'.',2) <> (CASE NEW.mime WHEN 'application/pdf' THEN 'pdf' WHEN 'image/png' THEN 'png' ELSE 'jpg' END) THEN
   RAISE EXCEPTION 'Ruta de archivo no válida';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ent_validar_archivo BEFORE INSERT ON public.ent_archivos
 FOR EACH ROW EXECUTE FUNCTION ent_privado.validar_archivo();
CREATE FUNCTION ent_privado.validar_asistencia() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM public.ent_sesiones s JOIN public.ent_grupos g ON g.id=s.grupo_id
  JOIN public.jugadores j ON j.categoria_id=g.categoria_id AND coalesce(j.institucion,'Club Juventud')=g.institucion
  WHERE s.id=NEW.sesion_id AND j.id=NEW.jugador_id
 ) THEN RAISE EXCEPTION 'El deportista no pertenece a esta institución y categoría'; END IF;
 NEW.updated_at=now(); RETURN NEW;
END $$;
CREATE TRIGGER ent_validar_asistencia BEFORE INSERT OR UPDATE ON public.ent_asistencias
 FOR EACH ROW EXECUTE FUNCTION ent_privado.validar_asistencia();
REVOKE ALL ON FUNCTION ent_privado.validar_sesion(), ent_privado.validar_archivo(), ent_privado.validar_asistencia() FROM PUBLIC;

CREATE FUNCTION public.ent_confirmar_archivo(p_archivo uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.ent_archivos a WHERE a.id=p_archivo AND ent_privado.editar_sesion(a.sesion_id)) THEN
   RAISE EXCEPTION 'No autorizado';
 END IF;
 UPDATE public.ent_archivos a SET confirmado=true WHERE a.id=p_archivo AND EXISTS (
   SELECT 1 FROM storage.objects o WHERE o.bucket_id='entrenamientos-privados' AND o.name=a.ruta
 );
 IF NOT FOUND THEN RAISE EXCEPTION 'El archivo todavía no está almacenado'; END IF;
END $$;
CREATE FUNCTION public.ent_guardar_asistencia(p_sesion uuid, p_registros jsonb) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
 IF NOT ent_privado.editar_sesion(p_sesion) THEN RAISE EXCEPTION 'No autorizado'; END IF;
 IF jsonb_typeof(p_registros)<>'array' OR jsonb_array_length(p_registros)>300 THEN
   RAISE EXCEPTION 'Lista de asistencia no válida';
 END IF;
 INSERT INTO public.ent_asistencias(sesion_id,jugador_id,estado)
 SELECT p_sesion,r.jugador_id,r.estado FROM jsonb_populate_recordset(null::public.ent_asistencias,p_registros) r
 ON CONFLICT(sesion_id,jugador_id) DO UPDATE SET estado=excluded.estado;
END $$;
REVOKE ALL ON FUNCTION public.ent_confirmar_archivo(uuid), public.ent_guardar_asistencia(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ent_confirmar_archivo(uuid), public.ent_guardar_asistencia(uuid,jsonb) TO authenticated;

REVOKE ALL ON public.ent_grupos,public.ent_asignaciones,public.ent_sesiones,public.ent_archivos,public.ent_asistencias FROM PUBLIC, anon, authenticated;
GRANT SELECT,INSERT ON public.ent_grupos TO authenticated;
GRANT SELECT,INSERT,DELETE ON public.ent_asignaciones TO authenticated;
GRANT SELECT,INSERT,UPDATE ON public.ent_sesiones TO authenticated;
GRANT SELECT,INSERT,DELETE ON public.ent_archivos TO authenticated;
GRANT SELECT,INSERT,UPDATE ON public.ent_asistencias TO authenticated;

INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 VALUES ('entrenamientos-privados','entrenamientos-privados',false,10485760,ARRAY['application/pdf','image/png','image/jpeg']);
CREATE POLICY ent_storage_lectura ON storage.objects FOR SELECT TO authenticated USING (
 bucket_id='entrenamientos-privados' AND EXISTS (SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name)
);
CREATE POLICY ent_storage_carga ON storage.objects FOR INSERT TO authenticated WITH CHECK (
 bucket_id='entrenamientos-privados' AND EXISTS (
  SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name AND NOT a.confirmado AND ent_privado.editar_sesion(a.sesion_id)
 )
);
CREATE POLICY ent_storage_retirar_pendiente ON storage.objects FOR DELETE TO authenticated USING (
 bucket_id='entrenamientos-privados' AND EXISTS (
  SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name AND NOT a.confirmado AND ent_privado.editar_sesion(a.sesion_id)
 )
);
-- Límites restrictivos para este bucket: una política antigua más amplia no debe
-- conceder acceso a sus objetos. Los demás buckets conservan su comportamiento.
CREATE POLICY ent_storage_limite_lectura ON storage.objects AS RESTRICTIVE FOR SELECT TO authenticated USING (
 bucket_id<>'entrenamientos-privados' OR EXISTS (SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name)
);
CREATE POLICY ent_storage_limite_carga ON storage.objects AS RESTRICTIVE FOR INSERT TO authenticated WITH CHECK (
 bucket_id<>'entrenamientos-privados' OR EXISTS (
  SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name AND NOT a.confirmado AND ent_privado.editar_sesion(a.sesion_id)
 )
);
CREATE POLICY ent_storage_limite_edicion ON storage.objects AS RESTRICTIVE FOR UPDATE TO authenticated
 USING (bucket_id<>'entrenamientos-privados') WITH CHECK (bucket_id<>'entrenamientos-privados');
CREATE POLICY ent_storage_limite_borrado ON storage.objects AS RESTRICTIVE FOR DELETE TO authenticated USING (
 bucket_id<>'entrenamientos-privados' OR EXISTS (
  SELECT 1 FROM public.ent_archivos a WHERE a.ruta=name AND NOT a.confirmado AND ent_privado.editar_sesion(a.sesion_id)
 )
);
CREATE POLICY ent_storage_limite_anon ON storage.objects AS RESTRICTIVE FOR ALL TO anon
 USING (bucket_id<>'entrenamientos-privados') WITH CHECK (bucket_id<>'entrenamientos-privados');
-- No se permite sobrescribir objetos ni editar/borrar archivos ya confirmados.
COMMIT;
