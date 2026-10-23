\set ON_ERROR_STOP on
CREATE FUNCTION public.test_igual(obtenido bigint, esperado bigint, mensaje text) RETURNS void LANGUAGE plpgsql AS $$
 BEGIN IF obtenido<>esperado THEN RAISE EXCEPTION '%: esperado %, obtenido %',mensaje,esperado,obtenido; END IF; END $$;
CREATE FUNCTION public.test_denegado(consulta text) RETURNS void LANGUAGE plpgsql AS $$
 DECLARE denegado boolean=false;
 BEGIN
  BEGIN EXECUTE consulta;
  EXCEPTION WHEN insufficient_privilege OR raise_exception OR check_violation OR foreign_key_violation THEN denegado=true; END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se permitió una operación prohibida: %',consulta; END IF;
 END $$;
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
INSERT INTO ent_grupos(id,institucion,categoria_id) VALUES
 ('10000000-0000-0000-0000-000000000001','Colegio Surcos',10),
 ('10000000-0000-0000-0000-000000000002','Club Juventud',10),
 ('10000000-0000-0000-0000-000000000003','Colegio Surcos',20);
INSERT INTO ent_asignaciones VALUES
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002'),
 ('10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000003');
SELECT test_denegado($q$INSERT INTO ent_asignaciones VALUES ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000007')$q$);
-- Sesión de otro grupo, registrada por administración.
INSERT INTO ent_sesiones(id,grupo_id,fecha,titulo,objetivos,contenido) VALUES
 ('20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002',current_date,'Club','Objetivo','Actividades'),
 ('20000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000003',current_date,'Surcos Sub14','Objetivo','Actividades');
UPDATE ent_sesiones SET estado='publicada';

SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),1,'Entrenador solo grupo asignado');
SELECT test_denegado($q$INSERT INTO ent_sesiones(grupo_id,fecha,titulo,objetivos,contenido) VALUES ('10000000-0000-0000-0000-000000000002',current_date,'Intrusión','Objetivo','Actividades')$q$);
INSERT INTO ent_sesiones(id,grupo_id,fecha,titulo,objetivos,contenido) VALUES
 ('20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',current_date,'Entrenamiento','Objetivo','Actividades');
INSERT INTO ent_archivos(id,sesion_id,tipo,ruta,nombre,mime,tamano) VALUES
 ('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','plan','20000000-0000-0000-0000-000000000001/30000000-0000-0000-0000-000000000001.pdf','plan.pdf','application/pdf',10);
SELECT test_denegado($q$SELECT ent_confirmar_archivo('30000000-0000-0000-0000-000000000001')$q$);
SELECT test_denegado($q$UPDATE ent_sesiones SET estado='publicada' WHERE id='20000000-0000-0000-0000-000000000001'$q$);
INSERT INTO storage.objects(bucket_id,name) VALUES ('entrenamientos-privados','20000000-0000-0000-0000-000000000001/30000000-0000-0000-0000-000000000001.pdf');
SELECT ent_confirmar_archivo('30000000-0000-0000-0000-000000000001');
SELECT ent_guardar_asistencia('20000000-0000-0000-0000-000000000001','[{"jugador_id":101,"estado":"presente"},{"jugador_id":102,"estado":"ausente"}]');
SELECT test_denegado($q$SELECT ent_guardar_asistencia('20000000-0000-0000-0000-000000000001','[{"jugador_id":101,"estado":"ausente"},{"jugador_id":103,"estado":"presente"}]')$q$);
SELECT test_igual((SELECT count(*) FROM ent_asistencias WHERE jugador_id=101 AND estado='presente'),1,'Asistencia se guarda de forma atómica');
SELECT test_denegado($q$UPDATE ent_sesiones SET grupo_id='10000000-0000-0000-0000-000000000002' WHERE id='20000000-0000-0000-0000-000000000001'$q$);
SELECT test_denegado($q$UPDATE ent_archivos SET confirmado=true$q$);

SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),1,'Representante solo categoría vinculada');
SELECT test_igual((SELECT count(*) FROM ent_sesiones),0,'Borradores no visibles para representante');
SELECT test_igual((SELECT count(*) FROM storage.objects),0,'Archivos de borrador no visibles');
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
UPDATE ent_sesiones SET estado='publicada' WHERE id='20000000-0000-0000-0000-000000000001';

SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',false);
SELECT test_igual((SELECT count(*) FROM ent_sesiones),1,'Sesión publicada de su categoría');
SELECT test_igual((SELECT count(*) FROM ent_asistencias),1,'Representante solo asistencia propia');
SELECT test_igual((SELECT count(*) FROM ent_asistencias WHERE jugador_id=102),0,'No ve asistencia de otro menor');
SELECT test_igual((SELECT count(*) FROM storage.objects),1,'Puede observar archivo confirmado de su categoría');
SELECT test_denegado($q$SELECT ent_guardar_asistencia('20000000-0000-0000-0000-000000000001','[{"jugador_id":101,"estado":"ausente"}]')$q$);
SELECT test_denegado($q$INSERT INTO storage.objects(bucket_id,name) VALUES ('entrenamientos-privados','intruso.jpg')$q$);

SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000006',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),1,'Otro representante solo su grupo');
SELECT test_igual((SELECT count(*) FROM ent_asistencias),0,'Otro representante no ve asistencia ajena');
SELECT test_igual((SELECT count(*) FROM storage.objects),0,'Otro representante no ve archivos ajenos');
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),2,'Autoridad solo Surcos');
SELECT test_igual((SELECT count(*) FROM ent_sesiones),2,'Autoridad ve sesiones Surcos publicadas');
SELECT test_igual((SELECT count(*) FROM ent_asistencias),2,'Autoridad ve asistencia de categoría');
SELECT test_denegado($q$SELECT ent_guardar_asistencia('20000000-0000-0000-0000-000000000001','[]')$q$);
SELECT test_denegado($q$INSERT INTO ent_grupos(institucion,categoria_id) VALUES ('Club Juventud',20)$q$);
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
SELECT test_igual((SELECT count(*) FROM ent_sesiones),1,'Otro entrenador no ve sesiones sin asignación');
SELECT test_denegado($q$SELECT ent_confirmar_archivo('30000000-0000-0000-0000-000000000001')$q$);
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000007',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),0,'Inactivo sin acceso');
SELECT test_igual((SELECT count(*) FROM ent_sesiones),0,'Inactivo sin sesiones');
SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
SELECT test_igual((SELECT count(*) FROM ent_grupos),3,'Administración ve todos los grupos');
SELECT test_igual((SELECT count(*) FROM ent_sesiones),3,'Administración ve todo');
SELECT test_igual((SELECT count(*) FROM ent_asistencias),2,'Administración ve toda asistencia');
SELECT test_igual((SELECT count(*) FROM storage.objects),1,'Administración ve todos los archivos');
RESET ROLE;
SET ROLE anon;
SELECT public.test_denegado('SELECT * FROM public.ent_sesiones');
SELECT public.test_denegado('SELECT * FROM public.ent_grupos');
RESET ROLE;
SELECT 'Permisos de entrenamientos: pruebas completadas' AS resultado;
