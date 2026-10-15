import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorEstado, Cargando } from '../components/Estado';
import { useEstadoDatos } from '../data/DatosContext';
import { useRevision } from '../data/RevisionContext';

const MENSAJE_NO_REGISTRADA =
  'Ese número no está registrado como profesora. Pídele a tu coordinadora que lo vincule a tu curso.';

export function ProfesoraIngreso() {
  const navegar = useNavigate();
  const estadoDatos = useEstadoDatos();
  const { ingresar, modo, profesorasDemo } = useRevision();
  const [telefono, setTelefono] = useState('');
  const [procesando, setProcesando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function intentarIngreso(numero: string) {
    setProcesando(numero);
    setError(null);
    try {
      const profesora = await ingresar(numero);
      if (!profesora) {
        setError(MENSAJE_NO_REGISTRADA);
        return;
      }
      navegar('/profesora/inicio', { replace: true });
    } catch (causa: unknown) {
      setError(
        causa instanceof Error
          ? causa.message
          : 'No se pudo iniciar sesión. Inténtalo nuevamente.',
      );
    } finally {
      setProcesando(null);
    }
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    void intentarIngreso(telefono);
  }

  return (
    <section className="ingreso-profesora" aria-labelledby="titulo-ingreso-profesora">
      <div className="panel ingreso-profesora__panel">
        <h2 id="titulo-ingreso-profesora">Ingreso de profesoras</h2>
        <p className="ficha-descripcion">
          Ingresa el número de WhatsApp con el que envías tus observaciones.
        </p>

        {modo === 'demo' && (
          <p className="aviso-demo" role="status">
            <strong>Modo demostración</strong>: usa un número ficticio de la lista.
          </p>
        )}

        <form className="formulario-ingreso" onSubmit={enviar}>
          <label htmlFor="telefono-profesora">Número de WhatsApp</label>
          <input
            id="telefono-profesora"
            name="telefono"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={telefono}
            onChange={(evento) => setTelefono(evento.target.value)}
            placeholder="Ej.: +56 9 1234 5678"
            required
          />
          <button type="submit" disabled={procesando !== null || estadoDatos.estado !== 'listo'}>
            {procesando === telefono ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>

        {estadoDatos.estado === 'cargando' && <Cargando mensaje="Cargando datos de acceso…" />}
        {estadoDatos.estado === 'error' && (
          <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estadoDatos.mensaje}`} />
        )}
        {error && <ErrorEstado mensaje={error} />}
      </div>

      {modo === 'demo' && estadoDatos.estado === 'listo' && (
        <section className="panel" aria-labelledby="titulo-profesoras-demo">
          <h3 id="titulo-profesoras-demo">Profesoras de demostración</h3>
          {profesorasDemo.length === 0 ? (
            <p className="estado">No hay profesoras de demostración disponibles.</p>
          ) : (
            <ul className="lista-demo">
              {profesorasDemo.map((profesora) => (
                <li key={profesora.idEducadora}>
                  <div>
                    <strong>{profesora.idEducadora}</strong>
                    <span>{profesora.telefono}</span>
                    <span>
                      {profesora.cursos.map((curso) => `${curso.idJardin} · ${curso.salaGrupo}`).join(', ') || 'Sin curso'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => void intentarIngreso(profesora.telefono)}
                    disabled={procesando !== null}
                  >
                    {procesando === profesora.telefono ? 'Ingresando…' : 'Ingresar'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </section>
  );
}
