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
  DOMINIOS,
} from '../domain/experiencia';
import { estadoManifestaciones, planEstimulacion } from '../domain/estimulacion';
import { ninosEnAlcance } from '../domain/trayectoria';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tarjeta } from '../components/Tarjeta';
import { BadgeNivel } from '../components/BadgeNivel';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { GraficoTrayectoriaNivel } from '../components/GraficoTrayectoriaNivel';
import { SelectorTrayectoriaNino } from '../components/SelectorTrayectoriaNino';
import { GraficoDistribucion } from '../components/GraficoDistribucion';
import { GraficoBarras } from '../components/GraficoBarras';
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
      {estado.estado === 'listo' && <OrigenAlertas datos={estado.datos} />}
    </>
  );
}

type Foco = 'todos' | 'alerta' | 'al-dia';

function PanelParvularia({ datos, cursos }: { datos: Datos; cursos: ResumenCurso[] }) {
  const [salaClave, setSalaClave] = useState<string | null>(null);
  const [ninoSel, setNinoSel] = useState<string | null>(null);
  const [dominioSel, setDominioSel] = useState('__todos__');
  const [foco, setFoco] = useState<Foco>('todos');

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
  const fichasVisibles = fichasSala
    .filter((f) =>
      foco === 'todos' ? true : foco === 'alerta' ? f.alerta : !f.alerta,
    )
    .sort((a, b) => (a.brecha ?? 0) - (b.brecha ?? 0));
  const nAlerta = fichasSala.filter((f) => f.alerta).length;

  const ninoActivo =
    (ninoSel && fichasSala.some((f) => f.nino.idNino === ninoSel) ? ninoSel : undefined) ??
    fichasSala.find((f) => f.alerta)?.nino.idNino ??
    fichasSala[0]?.nino.idNino ??
    '';
  const ficha = fichasSala.find((f) => f.nino.idNino === ninoActivo);

  const claveActiva = cursoActivo
    ? claveCurso(cursoActivo.idJardin, cursoActivo.salaGrupo)
    : '';

  const alumnosSala = cursoActivo
    ? alumnosDeCurso(datos, cursoActivo.idJardin, cursoActivo.salaGrupo, HOY)
    : [];
  const distribucionSala = distribucionNiveles(alumnosSala);

  return (
    <div className="vista-filtrada">
      <aside className="columna-filtros" aria-label="Filtros de la vista">
        <h3 className="columna-filtros__titulo">Filtros</h3>

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
              <option
                key={claveCurso(c.idJardin, c.salaGrupo)}
                value={claveCurso(c.idJardin, c.salaGrupo)}
              >
                {c.nombreJardin} · Sala {c.salaGrupo} ({c.totalNinos})
              </option>
            ))}
          </select>
        </div>

        <div className="buscador">
          <label htmlFor="sel-nino">Niño o niña</label>
          <select
            id="sel-nino"
            value={ninoActivo}
            onChange={(e) => setNinoSel(e.target.value)}
          >
            {fichasSala.map((f) => (
              <option key={f.nino.idNino} value={f.nino.idNino}>
                {f.nino.idNino}
                {f.alerta ? ' · necesita apoyo' : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="buscador">
          <label htmlFor="sel-dominio">Dominio</label>
          <select
            id="sel-dominio"
            value={dominioSel}
            onChange={(e) => setDominioSel(e.target.value)}
          >
            <option value="__todos__">Todos los dominios</option>
            {DOMINIOS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="buscador">
          <label htmlFor="sel-foco">Mostrar</label>
          <select
            id="sel-foco"
            value={foco}
            onChange={(e) => setFoco(e.target.value as Foco)}
          >
            <option value="todos">Todos los niños/as ({fichasSala.length})</option>
            <option value="alerta">Solo quienes necesitan apoyo ({nAlerta})</option>
            <option value="al-dia">
              Solo quienes están al día ({fichasSala.length - nAlerta})
            </option>
          </select>
        </div>

        <p className="columna-filtros__ayuda">
          Los filtros cambian la lista, los gráficos y la ficha sin recargar la página.
        </p>
      </aside>

      <div className="vista-contenido">
        <section className="panel foco" aria-label="Niños y niñas que requieren apoyo">
          <h3 className="seccion__titulo">Niños y niñas de esta sala</h3>
          {fichasVisibles.length === 0 ? (
            <p className="ficha-descripcion">
              Ningún niño/a coincide con el filtro. Cambia “Mostrar” para ver el resto de la
              sala.
            </p>
          ) : (
            <>
              <p className="ficha-descripcion">
                {nAlerta} de {fichasSala.length} niños/as requieren apoyo. El registro
                automático te devuelve horas cada semana: enfócalas aquí.
              </p>
              <ul className="lista-alertas">
                {fichasVisibles.map((f) => (
                  <li key={f.nino.idNino}>
                    <button
                      type="button"
                      className={f.nino.idNino === ninoActivo ? 'activo' : undefined}
                      onClick={() => setNinoSel(f.nino.idNino)}
                    >
                      <span className="lista-alertas__id">{f.nino.idNino}</span>
                      <span className="lista-alertas__meta">
                        Nivel {f.nivelVigente ?? '—'} · esperado {f.nivelEsperado ?? '—'}
                        {f.rezagoRelativo ? ' · bajo el promedio de la sala' : ''}
                      </span>
                      <BadgeAlerta activa={f.alerta} />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section aria-label="Niveles de la sala" className="panel">
          <GraficoDistribucion
            datos={distribucionSala}
            titulo="¿En qué nivel está cada niño y niña de tu sala?"
          />
        </section>

        {!ficha ? (
          <Vacio mensaje="Esta sala no tiene niños/as registrados." />
        ) : (
          <FichaAcompanamiento datos={datos} ficha={ficha} dominioSel={dominioSel} />
        )}
      </div>
    </div>
  );
}

function FichaAcompanamiento({
  datos,
  ficha,
  dominioSel = '__todos__',
}: {
  datos: Datos;
  ficha: FichaNino;
  dominioSel?: string;
}) {
  const diag = diagnostico(ficha);
  const cubiertos = dominiosCubiertos(ficha);
  const faltantes = dominiosFaltantes(ficha);
  const niveles = nivelPorNumero(datos.niveles);
  const nivelInfo = ficha.nivelVigente !== null ? niveles.get(ficha.nivelVigente) : undefined;
  const estadoMan = estadoManifestaciones(ficha);
  const plan = planEstimulacion(ficha);

  const filtrada = (d: string) => dominioSel === '__todos__' || d === dominioSel;
  const barrasDominio = estadoMan.porDominio
    .filter((d) => filtrada(d.dominio))
    .map((d) => ({ nombre: d.nombre, valor: d.observadas }));
  const observacionesVisibles = ficha.observaciones.filter((obs) =>
    dominioSel === '__todos__'
      ? true
      : obs.manifestaciones.some((m) => m.dominio === dominioSel),
  );
  const listaObservaciones = dominioSel === '__todos__'
    ? ficha.observaciones
    : observacionesVisibles;

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

      {ficha.alerta && plan.length > 0 && (
        <section aria-label="Acciones para estimular" className="panel estimulo">
          <h3 className="seccion__titulo">Acciones para estimular</h3>
          <p className="ficha-descripcion">
            Ideas para acompañar su desarrollo en la sala. Se priorizan los dominios sin
            evidencia o con el nivel más bajo; son sugerencias, no indicaciones clínicas.
          </p>
          <ol className="estimulo__lista">
            {plan.map((p) => (
              <li key={p.dominio} className="estimulo__item">
                <p className="estimulo__dominio">
                  {p.nombre}{' '}
                  <span className="estimulo__motivo">
                    {p.motivo === 'sin-evidencia' ? 'sin evidencia' : 'nivel más bajo'}
                  </span>
                </p>
                <ul className="estimulo__acciones">
                  {p.acciones.map((a) => (
                    <li key={a.titulo}>
                      <strong>{a.titulo}.</strong> {a.detalle}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section aria-label="Trayectoria del nivel" className="panel">
        <GraficoTrayectoriaNivel datos={datos} idNino={ficha.nino.idNino} />
        {nivelInfo && (
          <p className="ficha-descripcion">
            Nivel {nivelInfo.nivel}: {nivelInfo.nombreNivel}. {nivelInfo.descripcion}
          </p>
        )}
      </section>

      <section aria-label="Estado de las manifestaciones" className="panel">
        <h3 className="seccion__titulo">Estado de las manifestaciones</h3>
        <p className="ficha-descripcion">
          {estadoMan.total} manifestaciones observadas en {ficha.observaciones.length}{' '}
          {ficha.observaciones.length === 1 ? 'observación' : 'observaciones'}.
          {dominioSel !== '__todos__' && ' (filtro de dominio aplicado)'}
        </p>
        <ul className="estado-dominios">
          {estadoMan.porDominio
            .filter((d) => filtrada(d.dominio))
            .map((d) => (
              <li key={d.dominio} className={d.observadas === 0 ? 'sin-evidencia' : undefined}>
                <span className="dominio-tag">{d.nombre}</span>
                <span className="estado-dominios__dato">
                  {d.observadas === 0
                    ? 'sin evidencia'
                    : `${d.observadas} obs · nivel ${d.nivelPromedio?.toFixed(1)}`}
                </span>
              </li>
            ))}
        </ul>
        <GraficoBarras
          datos={barrasDominio}
          titulo="Manifestaciones observadas por dominio"
          etiquetaX="Manifestaciones observadas"
          etiquetaY="Dominio de desarrollo"
          unidad="manifestación"
          nota={
            barrasDominio.every((b) => b.valor === 0)
              ? 'Este niño/a todavía no tiene manifestaciones registradas en el dominio seleccionado.'
              : undefined
          }
        />
      </section>

      <section aria-label="De dónde viene la alerta" className="panel origen-alerta">
        <h3 className="seccion__titulo">De dónde viene esta alerta</h3>
        <p className="ficha-descripcion">
          La alerta no la inventa el sistema: sale de una regla simple comparando tres
          datos ya registrados.
        </p>
        <ul className="origen-lista">
          <li>
            <span className="origen-lista__dato">Nivel vigente: {ficha.nivelVigente ?? '—'}</span>
            <span className="origen-lista__fuente">
              Último nivel confirmado por la educadora en sus observaciones.
            </span>
          </li>
          <li>
            <span className="origen-lista__dato">Nivel esperado: {ficha.nivelEsperado ?? '—'}</span>
            <span className="origen-lista__fuente">
              Rango que corresponde a su edad ({ficha.edadMeses} meses) en la tabla de niveles.
            </span>
          </li>
          <li>
            <span className="origen-lista__dato">Diferencia: {ficha.brecha ?? '—'}</span>
            <span className="origen-lista__fuente">
              Vigente menos esperado. Hay alerta cuando la diferencia es -2 o menos.
            </span>
          </li>
        </ul>
        <p className={`origen-veredicto${ficha.alerta ? ' origen-veredicto--alerta' : ''}`}>
          {ficha.alerta
            ? `Alerta activa: está ${Math.abs(ficha.brecha ?? 0)} nivel${Math.abs(ficha.brecha ?? 0) === 1 ? '' : 'es'} por debajo de lo esperado para su edad.`
            : 'Sin alerta por edad: su nivel está dentro de lo esperado para su edad.'}
        </p>
        <p className="ficha-descripcion">
          {ficha.rezagoRelativo
            ? 'Además está bajo el promedio de su sala (rezago relativo), aunque su nivel por edad esté en rango.'
            : 'Comparado con su sala, está en el promedio o por sobre él.'}
        </p>
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
        {listaObservaciones.length === 0 ? (
          <Vacio mensaje="Sin observaciones registradas." />
        ) : (
          [...listaObservaciones]
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
                    {obs.manifestaciones
                      .filter((m) => filtrada(m.dominio))
                      .map((m) => (
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
  const [salaSel, setSalaSel] = useState('__todas__');
  const [foco, setFoco] = useState<Foco>('todos');
  const jardines = datos.jardines;

  const cursosJardin =
    jardinSel === '__todos__' ? cursos : cursos.filter((c) => c.idJardin === jardinSel);
  const cursosFiltrados =
    salaSel === '__todas__'
      ? cursosJardin
      : cursosJardin.filter((c) => claveCurso(c.idJardin, c.salaGrupo) === salaSel);

  const alumnosTodos = cursosFiltrados.flatMap((c) =>
    alumnosDeCurso(datos, c.idJardin, c.salaGrupo, HOY),
  );
  const alumnos = alumnosTodos.filter((a) =>
    foco === 'todos' ? true : foco === 'alerta' ? a.alerta : !a.alerta,
  );
  const ninosFiltrados = cursosFiltrados.flatMap((c) =>
    datos.ninos.filter((n) => n.idJardin === c.idJardin && n.salaGrupo === c.salaGrupo),
  );

  const nivelesVigentes = alumnosTodos
    .map((a) => a.nivelVigente)
    .filter((v): v is number => v !== null);
  const nPromedio = promedio(nivelesVigentes);
  const nAlertas = alumnosTodos.filter((a) => a.alerta).length;
  const distribucion = distribucionNiveles(alumnos);
  const tray = resumenTrayectorias(datos, ninosFiltrados);

  const fichasDir = ninosFiltrados
    .map((n) => fichaNino(datos, n.idNino, HOY))
    .filter((f): f is FichaNino => f !== null);
  const conteoDominio = new Map<string, number>();
  for (const f of fichasDir) {
    for (const o of f.observaciones) {
      for (const m of o.manifestaciones) {
        conteoDominio.set(m.dominio, (conteoDominio.get(m.dominio) ?? 0) + 1);
      }
    }
  }
  const barrasDominio = DOMINIOS.map((d) => ({
    nombre: d.nombre,
    valor: conteoDominio.get(d.id) ?? 0,
  }));

  const alertasPorSala = cursosFiltrados
    .map((c) => ({
      nombre: `${c.nombreJardin} · S${c.salaGrupo}`,
      valor: c.totalAlertas,
    }))
    .filter((x) => x.valor > 0)
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 10);

  const salasCompletas = cursosFiltrados.filter(
    (c) => c.totalNinos > 0 && c.totalAlertas === c.totalNinos,
  );

  return (
    <div className="vista-filtrada">
      <aside className="columna-filtros" aria-label="Filtros de la vista">
        <h3 className="columna-filtros__titulo">Filtros</h3>

        <div className="buscador">
          <label htmlFor="sel-jardin">Jardín</label>
          <select id="sel-jardin" value={jardinSel} onChange={(e) => {
            setJardinSel(e.target.value);
            setSalaSel('__todas__');
          }}>
            <option value="__todos__">Todos los jardines</option>
            {jardines.map((j) => (
              <option key={j.idJardin} value={j.idJardin}>
                {j.nombreFantasia} · {j.comuna}
              </option>
            ))}
          </select>
        </div>

        <div className="buscador">
          <label htmlFor="sel-sala-dir">Sala</label>
          <select id="sel-sala-dir" value={salaSel} onChange={(e) => setSalaSel(e.target.value)}>
            <option value="__todas__">Todas las salas</option>
            {cursosJardin.map((c) => (
              <option key={claveCurso(c.idJardin, c.salaGrupo)} value={claveCurso(c.idJardin, c.salaGrupo)}>
                {c.nombreJardin} · Sala {c.salaGrupo}
              </option>
            ))}
          </select>
        </div>

        <div className="buscador">
          <label htmlFor="sel-foco-dir">Mostrar</label>
          <select id="sel-foco-dir" value={foco} onChange={(e) => setFoco(e.target.value as Foco)}>
            <option value="todos">Todos ({alumnosTodos.length})</option>
            <option value="alerta">Solo con alerta ({nAlertas})</option>
            <option value="al-dia">Solo al día ({alumnosTodos.length - nAlertas})</option>
          </select>
        </div>

        <p className="columna-filtros__ayuda">
          Los filtros ajustan los indicadores y los gráficos de esta vista.
        </p>
      </aside>

      <div className="vista-contenido">
        <section aria-label="Resumen" className="tarjetas">
          <Tarjeta etiqueta="Salas" valor={String(cursosFiltrados.length)} descripcion="Sala y nivel de grupo" />
          <Tarjeta etiqueta="Niños y niñas" valor={String(alumnosTodos.length)} descripcion="Matriculados" />
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

        <section aria-label="Trayectoria de un niño/a" className="panel">
          <SelectorTrayectoriaNino
            datos={datos}
            ninos={ninosEnAlcance(ninosFiltrados, {
              rol: 'directora',
              idJardin: jardinSel === '__todos__' ? null : jardinSel,
            })}
            titulo="Trayectoria de nivel de un niño/a de la selección"
          />
        </section>

        {salasCompletas.length > 0 && (
          <section aria-label="Salas con alerta total" className="panel origen-alerta">
            <h3 className="seccion__titulo">Salas donde el 100% necesita apoyo</h3>
            <p className="ficha-descripcion">
              En estas salas todos los niños/as están por debajo de lo esperado para su edad.
              Revisa si es un grupo de edades mayores o si faltan observaciones recientes.
            </p>
            <ul className="origen-lista">
              {salasCompletas.map((c) => (
                <li key={claveCurso(c.idJardin, c.salaGrupo)}>
                  <span className="origen-lista__dato">
                    {c.nombreJardin} · Sala {c.salaGrupo}
                  </span>
                  <span className="origen-lista__fuente">
                    {c.totalAlertas} de {c.totalNinos} con alerta · nivel promedio{' '}
                    {formatearPromedio(c.nivelPromedio)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {alumnos.length === 0 ? (
          <Vacio mensaje="No hay niños y niñas en la selección." />
        ) : (
          <>
            <section aria-label="Distribución por nivel" className="panel">
              <GraficoDistribucion datos={distribucion} />
            </section>

            <section aria-label="Alertas por sala" className="panel">
              <GraficoBarras
                datos={alertasPorSala}
                titulo="¿En qué salas se concentra el apoyo requerido?"
                etiquetaX="Niños/as con alerta"
                etiquetaY="Sala"
                unidad="alerta"
                nota={
                  alertasPorSala.length === 0
                    ? 'Ninguna sala de la selección tiene niños/as con alerta.'
                    : 'Se muestran las 10 salas con más alertas.'
                }
              />
            </section>

            <section aria-label="Manifestaciones por dominio" className="panel">
              <GraficoBarras
                datos={barrasDominio}
                titulo="¿Qué dominios concentran las manifestaciones registradas?"
                etiquetaX="Manifestaciones observadas"
                etiquetaY="Dominio de desarrollo"
                unidad="manifestación"
                nota="Todos los dominios deberían tener evidencia; los vacíos indican dónde observar más."
              />
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
      </div>
    </div>
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

function OrigenAlertas({ datos }: { datos: Datos }) {
  const fichas = datos.ninos
    .map((n) => fichaNino(datos, n.idNino, HOY))
    .filter((f): f is FichaNino => f !== null);
  const conNivel = fichas.filter(
    (f) => f.nivelVigente !== null && f.nivelEsperado !== null,
  );
  const enAlerta = conNivel.filter((f) => f.alerta);
  const pct = conNivel.length ? Math.round((100 * enAlerta.length) / conNivel.length) : 0;
  const esperadoAlto = conNivel.filter((f) => (f.nivelEsperado ?? 0) >= 8).length;
  const pctEsperadoAlto = conNivel.length
    ? Math.round((100 * esperadoAlto) / conNivel.length)
    : 0;

  return (
    <section className="panel origen-alerta" aria-label="De dónde provienen las alertas">
      <h3 className="seccion__titulo">De dónde provienen las alertas</h3>
      <p className="ficha-descripcion">
        La alerta sale de comparar dos valores ya registrados, con una regla fija:
        hay alerta cuando <strong>nivel vigente − nivel esperado por edad ≤ −2</strong>.
        No es un juicio del sistema ni una predicción: es una resta entre el último nivel
        que confirmó la educadora y el rango que corresponde a la edad del niño/a.
      </p>
      <ul className="origen-lista">
        <li>
          <span className="origen-lista__dato">
            {enAlerta.length} de {conNivel.length} niños/as en alerta ({pct}%)
          </span>
          <span className="origen-lista__fuente">
            Sobre el total con nivel vigente y esperado calculables en el conjunto de datos.
          </span>
        </li>
        <li>
          <span className="origen-lista__dato">
            {esperadoAlto} niños/as ({pctEsperadoAlto}%) con nivel esperado 8 o 9
          </span>
          <span className="origen-lista__fuente">
            Son los de mayor edad: con 18–31 meses, la tabla de niveles espera 8–9.
          </span>
        </li>
      </ul>
      <p className="ficha-descripcion">
        En este conjunto de datos de ejemplo el porcentaje de alerta es alto porque las
        edades se concentran entre 18 y 31 meses (esperado 8–9) mientras los niveles
        observados se reparten de 1 a 9. Es un rasgo del dataset sintético E-1, no un
        error del cálculo: con los datos reales de cada jardín, la proporción depende de la
        brecha real entre lo observado y lo esperado.
      </p>
    </section>
  );
}

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
