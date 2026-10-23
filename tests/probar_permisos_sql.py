"""Ejecuta solo contra un contenedor Docker LOCAL de pruebas, nunca una URL de BD."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


def main():
    contenedor = sys.argv[1] if len(sys.argv) > 1 else 'juventud-entrenamientos-test'
    raiz = Path(__file__).resolve().parents[1]
    entorno = {k: v for k, v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')}
    comando = ['docker','--host=unix:///var/run/docker.sock','exec','-i',contenedor]
    for variante in ('bigint', 'uuid'):
        nombre = 'ent_test_' + uuid4().hex
        subprocess.run(comando + ['createdb','-U','postgres',nombre], env=entorno, check=True)
        try:
            base = (raiz/'tests/sql/base_entrenamientos.sql').read_text()
            permisos = (raiz/'tests/sql/permisos_entrenamientos.sql').read_text()
            if variante == 'uuid':
                import re
                base = base.replace('id bigint', 'id uuid')
                base = re.sub(r'\b(10|20|101|102|103|104)\b', lambda m: "'00000000-0000-0000-0000-" + m[0].zfill(12) + "'::uuid", base)
                permisos = """
                SELECT CASE WHEN atttypid='uuid'::regtype THEN true ELSE false END AS clave_uuid
                 FROM pg_attribute WHERE attrelid='public.ent_asistencias'::regclass AND attname='jugador_id';
                SET ROLE authenticated;
                SELECT set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
                INSERT INTO ent_grupos(id,institucion,categoria_id) VALUES ('10000000-0000-0000-0000-000000000001','Colegio Surcos','00000000-0000-0000-0000-000000000010');
                INSERT INTO ent_sesiones(id,grupo_id,fecha,titulo,objetivos,contenido) VALUES ('20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',current_date,'UUID','Objetivo','Contenido');
                SELECT ent_guardar_asistencia('20000000-0000-0000-0000-000000000001','[{"jugador_id":"00000000-0000-0000-0000-000000000101","estado":"presente"}]');
                DO $$ BEGIN IF (SELECT count(*) FROM ent_asistencias)<>1 THEN RAISE EXCEPTION 'Asistencia UUID fallida'; END IF; END $$;
                SELECT 'Claves UUID: migración y asistencia correctas';
                """
            sql = '\n'.join([base, (raiz/'migrations/001_espacios_entrenamiento.sql').read_text(), permisos])
            subprocess.run(comando + ['psql','-U','postgres','-d',nombre,'-v','ON_ERROR_STOP=1'], input=sql, text=True, env=entorno, check=True)
        finally:
            subprocess.run(comando + ['dropdb','-U','postgres',nombre], env=entorno, check=True)



if __name__ == '__main__':
    main()
