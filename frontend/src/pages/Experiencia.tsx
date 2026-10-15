import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Datos } from '../data/cargar';
import { useEstadoDatos } from '../data/DatosContext';
import {
  alumnosDeCurso,
  claveCurso,
  distribucionNiveles,
  fichaNino,
  nivelPorNumero,
  resumenCursos,
  type FichaNino,
  type ResumenCurso,
} from '../domain/consultas';
import { promedio } from '../domain/metrics';
import { formatearPromedio } from '../domain/formato';
import {
  diagnostico,
  dominiosCubiertos,
  dominiosFaltantes,
  nombreDominio,
  resumenTrayectorias,
} from '../domain/experiencia';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tarjeta } from '../components/Tarjeta';
import { BadgeNivel } from '../components/BadgeNivel';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { GraficoTrayectoria } from '../components/GraficoTrayectoria';
import { GraficoDistribucion } from '../components/GraficoDistribucion';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

const HOY = new Date();

type Rol = 'parvularia' | 'directora';

export function Experiencia() {
  const estado = useEstadoDatos();
  const [rol, setRol] = useState<Rol>('parvularia');
  const cursos = estado.estado === 'listo' ? resumenCursos(estado.datos, HOY) : [];

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Acompañamiento' }]} />
      <h2>Acompañamiento y decisiones</h2>
      <p className="ayuda">
        La trayectoria de cada niño o niña, su nivel frente a lo esperado para la
        edad y las señales para decidir a quién acompañar. Elige tu rol según lo que
        necesites hacer hoy.
      </p>

      <div className="roles" role="tablist" aria-label="Vista según rol">
        <button
          type="button"
          role="tab"
          aria-selected={rol === 'parvularia'}
          className={rol === 'parvularia' ? 'activo' : undefined}
          onClick={() => setRol('parvularia')}
        >
          Parvularia
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={rol === 'directora'}
          className={rol === 'directora' ? 'activo' : undefined}
          onClick={() => setRol('directora')}
        >
          Directora
        </button>
      </div>

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}

      {estado.estado === 'listo' && rol === 'parvularia' && (
        <PanelParvularia datos={estado.datos} cursos={cursos} />
      )}
      {estado.estado === 'listo' && rol === 'directora' && (
        <PanelDirectora datos={estado.datos} cursos={cursos} />
      )}

      {estado.estado === 'listo' && <Pipeline />}
    </>
  );
}

function PanelParvularia({ datos, cursos }: { datos: Datos; cursos: ResumenCurso[] }) {
  const [salaClave, setSalaClave] = useState<string | null>(null);
  const [ninoSel, setNinoSel] = useState<string | null>(null);

  if (cursos.length === 0) {
    return <Vacio mensaje="No hay salas con niños y niñas registrados." />;
  }

  const cursoActivo =
    cursos.find((c) => claveCurso(c.idJardin, c.salaGrupo) === salaClave) ?? cursos[0];
  const ninosSala = cursoActivo
    ? datos.ninos.filter(
        (n) => n.idJardin === cursoActivo.idJardin && n.salaGrupo === cursoActivo.salaGrupo,
      )
    : [];
  const fichasSala = ninosSala
    .map((n) => fichaNino(datos, n.idNino, HOY))
    .filter((f): f is FichaNino => f !== null);

  const ninoActivo =
    (ninoSel && fichasSala.some((f) => f.nino.idNino === ninoSel) ? ninoSel : undefined) ??
    fichasSala.find((f) => f.alerta)?.nino.idNino ??
    fichasSala[0]?.nino.idNino ??
    '';
  const ficha = fichasSala.find((f) => f.nino.idNino === ninoActivo);

  const claveActiva = cursoActivo
    ? claveCurso(cursoActivo.idJardin, cursoActivo.salaGrupo)
    : '';

  return (
    <>
      <div className="selector-duo">
        <div className="buscador">
          <label htmlFor="sel-sala">Sala</label>
          <select
            id="sel-sala"
            value={claveActiva}
            onChange={(e) => {
              setSalaClave(e.target.value);
              setNinoSel(null);
            }}
          >
            {cursos.map((c) => (
              <option key={claveCurso(c.idJardin, c.salaGrupo)} value={claveCurso(c.idJardin, c.salaGrupo)}>
                {c.nombreJardin} · Sala {c.salaGrupo} ({c.totalNinos})
              </option>
            ))}
          </select>
        </div>
        <div className="buscador">
          <label htmlFor="sel-nino">Niño o niña</label>
          <select id="sel-nino" value={ninoActivo} onChange={(e) => setNinoSel(e.target.value)}>
            {fichasSala.map((f) => (
              <option key={f.nino.idNino} value={f.nino.idNino}>
                {f.nino.idNino}
                {f.alerta ? ' · necesita apoyo' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!ficha ? (
        <Vacio mensaje="Esta sala no tiene niños/as registrados." />
      ) : (
        <FichaAcompanamiento datos={datos} ficha={ficha} />
      )}
    </>
  );
}

function FichaAcompanamiento({ datos, ficha }: { datos: Datos; ficha: FichaNino }) {
  const diag = diagnostico(ficha);
  const cubiertos = dominiosCubiertos(ficha);
  const faltantes = dominiosFaltantes(ficha);
  const niveles = nivelPorNumero(datos.niveles);
  const nivelInfo = ficha.nivelVigente !== null ? niveles.get(ficha.nivelVigente) : undefined;
  const trayectoria = ficha.observaciones.map((o) => ({
    fecha: o.fechaObservacion,
    nivel: o.nivelEstimado,
  }));

  return (
    <>
      <section aria-label="Resumen del niño/a" className="tarjetas">
        <Tarjeta etiqueta="Edad" valor={`${ficha.edadMeses} meses`} descripcion="Meses cumplidos" />
        <Tarjeta
          etiqueta="Nivel actual"
          valor={ficha.nivelVigente?.toString() ?? '—'}
          descripcion="Según la última observación"
        />
        <Tarjeta
          etiqueta="Nivel esperado"
          valor={ficha.nivelEsperado?.toString() ?? '—'}
          descripcion="Según su edad"
        />
        <Tarjeta
          etiqueta="Diferencia"
          valor={
            ficha.brecha === null
              ? '—'
              : ficha.brecha > 0
                ? `+${ficha.brecha}`
                : String(ficha.brecha)
          }
          descripcion="Nivel actual menos esperado"
          alerta={ficha.alerta}
        />
      </section>

      <section className={`decision decision--${diag.estado}`} aria-label="Recomendación">
        <h3 className="seccion__titulo">
          {diag.titulo} {ficha.alerta && <BadgeAlerta activa />}
        </h3>
        <p>{diag.detalle}</p>
      </section>

      <section aria-label="Trayectoria del nivel" className="panel">
        {trayectoria.length === 0 ? (
          <>
            <h3 className="seccion__titulo">Trayectoria</h3>
            <Vacio mensaje="Sin observaciones registradas todavía." />
          </>
        ) : (
          <GraficoTrayectoria datos={trayectoria} />
        )}
        {nivelInfo && (
          <p className="ficha-descripcion">
            Nivel {nivelInfo.nivel}: {nivelInfo.nombreNivel}. {nivelInfo.descripcion}
          </p>
        )}
      </section>

      <section aria-label="Focos de observación" className="panel">
        <h3 className="seccion__titulo">Dominios con evidencia</h3>
        {cubiertos.length === 0 ? (
          <p className="ficha-descripcion">Todavía sin evidencia por dominio.</p>
        ) : (
          <div className="chips">
            {cubiertos.map((id) => (
              <span className="chip" key={id}>
                {nombreDominio(id)}
              </span>
            ))}
          </div>
        )}
        {faltantes.length > 0 && (
          <>
            <h3 className="seccion__titulo">Sin evidencia todavía</h3>
            <div className="chips">
              {faltantes.map((id) => (
                <span className="chip chip--pend" key={id}>
                  {nombreDominio(id)}
                </span>
              ))}
            </div>
            <p className="ficha-descripcion">
              Sugerencia: en la próxima observación, registra evidencia de{' '}
              {faltantes.map(nombreDominio).join(', ').toLowerCase()}.
            </p>
          </>
        )}
      </section>

      <section aria-label="Observaciones" className="panel">
        <h3 className="seccion__titulo">Cómo se construyó este nivel</h3>
        {ficha.observaciones.length === 0 ? (
          <Vacio mensaje="Sin observaciones registradas." />
        ) : (
          [...ficha.observaciones]
            .slice()
            .reverse()
            .map((obs) => (
              <article key={obs.idObservacion} className="observacion">
                <div className="observacion__cabecera">
                  <span className="observacion__fecha">{obs.fechaObservacion}</span>
                  <span className="observacion__formato">{obs.formatoCaptura}</span>
                  <BadgeNivel nivel={obs.nivelEstimado} />
                </div>
                {obs.manifestaciones.length > 0 ? (
                  <ul>
                    {obs.manifestaciones.map((m) => (
                      <li key={m.idManifestacion}>
                        {m.textoObservable}{' '}
                        <span className="dominio-tag">{nombreDominio(m.dominio)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="ficha-descripcion">Sin manifestaciones registradas.</p>
                )}
              </article>
            ))
        )}
      </section>
    </>
  );
}

function PanelDirectora({ datos, cursos }: { datos: Datos; cursos: ResumenCurso[] }) {
  const [jardinSel, setJardinSel] = useState('__todos__');
  const jardines = datos.jardines;

  const cursosFiltrados =
    jardinSel === '__todos__' ? cursos : cursos.filter((c) => c.idJardin === jardinSel);
  const alumnos = cursosFiltrados.flatMap((c) =>
    alumnosDeCurso(datos, c.idJardin, c.salaGrupo, HOY),
  );
  const ninosFiltrados =
    jardinSel === '__todos__' ? datos.ninos : datos.ninos.filter((n) => n.idJardin === jardinSel);

  const nivelesVigentes = alumnos
    .map((a) => a.nivelVigente)
    .filter((v): v is number => v !== null);
  const nPromedio = promedio(nivelesVigentes);
  const nAlertas = alumnos.filter((a) => a.alerta).length;
  const distribucion = distribucionNiveles(alumnos);
  const tray = resumenTrayectorias(datos, ninosFiltrados);

  return (
    <>
      <div className="buscador">
        <label htmlFor="sel-jardin">Jardín</label>
        <select id="sel-jardin" value={jardinSel} onChange={(e) => setJardinSel(e.target.value)}>
          <option value="__todos__">Todos los jardines</option>
          {jardines.map((j) => (
            <option key={j.idJardin} value={j.idJardin}>
              {j.nombreFantasia} · {j.comuna}
            </option>
          ))}
        </select>
      </div>

      <section aria-label="Resumen" className="tarjetas">
        <Tarjeta etiqueta="Salas" valor={String(cursosFiltrados.length)} descripcion="Sala y nivel de grupo" />
        <Tarjeta etiqueta="Niños y niñas" valor={String(alumnos.length)} descripcion="Matriculados" />
        <Tarjeta
          etiqueta="Nivel promedio"
          valor={formatearPromedio(nPromedio)}
          descripcion="Escala 1 a 9"
        />
        <Tarjeta
          etiqueta="Necesitan apoyo"
          valor={String(nAlertas)}
          descripcion="Muy por debajo de lo esperado"
          alerta={nAlertas > 0}
        />
      </section>

      <section aria-label="Impacto de la trayectoria" className="tarjetas">
        <Tarjeta etiqueta="Avanzan" valor={String(tray.avanzan)} descripcion="Suben de nivel" />
        <Tarjeta etiqueta="Se mantienen" valor={String(tray.planos)} descripcion="Sin cambio de nivel" />
        <Tarjeta
          etiqueta="Retroceden"
          valor={String(tray.retroceden)}
          descripcion="Bajan de nivel"
          alerta={tray.retroceden > 0}
        />
        <Tarjeta
          etiqueta="Sin seguimiento"
          valor={String(tray.sinSeguimiento)}
          descripcion="Con una o ninguna observación"
        />
      </section>

      {alumnos.length === 0 ? (
        <Vacio mensaje="No hay niños y niñas en la selección." />
      ) : (
        <>
          <section aria-label="Distribución por nivel" className="panel">
            <GraficoDistribucion datos={distribucion} />
          </section>

          <section aria-label="Salas" className="panel">
            <h3 className="seccion__titulo">Salas y apoyo requerido</h3>
            <Tabla
              descripcion="Resumen por sala con nivel promedio y cantidad de niños/as que necesitan apoyo"
              filas={cursosFiltrados}
              claveFila={(c) => claveCurso(c.idJardin, c.salaGrupo)}
              columnas={columnasSalas}
            />
          </section>
        </>
      )}
    </>
  );
}

const columnasSalas: Columna<ResumenCurso>[] = [
  {
    clave: 'jardin',
    encabezado: 'Jardín',
    valor: (c) => c.nombreJardin,
    render: (c) => <Link to={`/curso/${c.idJardin}/${c.salaGrupo}`}>{c.nombreJardin}</Link>,
  },
  { clave: 'comuna', encabezado: 'Comuna', valor: (c) => c.comuna },
  { clave: 'sala', encabezado: 'Sala', valor: (c) => c.salaGrupo },
  { clave: 'ninos', encabezado: 'Niños/as', numerica: true, valor: (c) => c.totalNinos },
  {
    clave: 'promedio',
    encabezado: 'Nivel promedio',
    numerica: true,
    valor: (c) => c.nivelPromedio,
    render: (c) => formatearPromedio(c.nivelPromedio),
  },
  {
    clave: 'alertas',
    encabezado: 'Necesitan apoyo',
    numerica: true,
    valor: (c) => c.totalAlertas,
  },
];

const PASOS = [
  {
    n: '1',
    titulo: 'WhatsApp',
    detalle: 'La parvularia envía una observación: texto, foto de un post-it, nota de voz o video.',
  },
  {
    n: '2',
    titulo: 'Normalizar (U2)',
    detalle: 'Transcribe y la visión del modelo convierten cualquier formato a texto limpio.',
  },
  {
    n: '3',
    titulo: 'IA generativa (U3)',
    detalle:
      'Amazon Bedrock · Claude Sonnet 5 elige entre las 90 manifestaciones del catálogo; la salida se valida con Pydantic (typesafe).',
  },
  {
    n: '4',
    titulo: 'Propuesta y confirmación (U4)',
    detalle:
      'El sistema propone un nivel con la evidencia; la educadora Confirma, Ajusta o Cancela. Solo su decisión cambia el nivel.',
  },
  {
    n: '5',
    titulo: 'Registro auditable (U5)',
    detalle: 'Observación, evidencia y nivel quedan trazables en una sola transacción.',
  },
];

function Pipeline() {
  return (
    <section className="panel tecnologia" aria-label="Cómo funciona">
      <div className="tecnologia__cabecera">
        <h3 className="seccion__titulo">La IA detrás de cada nivel</h3>
        <span className="tecnologia__sello">Construido con Kiro + AWS</span>
      </div>
      <p className="ficha-descripcion">
        Cada nivel que ves no se inventa: lo propone un modelo de IA generativa a
        partir de evidencia observable, y lo confirma la educadora. Así el
        registro baja de 4 horas por semana a casi cero sin perder el criterio
        pedagógico.
      </p>
      <ol className="pipeline">
        {PASOS.map((p) => (
          <li key={p.n} className="paso">
            <span className="paso__num" aria-hidden="true">
              {p.n}
            </span>
            <div>
              <p className="paso__titulo">{p.titulo}</p>
              <p className="paso__detalle">{p.detalle}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
