import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { NotificacionAdvertencia } from '../domain/tipos';
import { ListaAdvertencias } from './ListaAdvertencias';

export function CampanaNotificaciones({
  notificaciones,
}: {
  notificaciones: NotificacionAdvertencia[];
}) {
  const [abierta, setAbierta] = useState(false);
  const contenedorRef = useRef<HTMLDivElement>(null);
  const botonRef = useRef<HTMLButtonElement>(null);
  const idPanel = useId();
  const recientes = notificaciones.slice(0, 6);

  useEffect(() => {
    if (!abierta) {
      return;
    }

    function cerrarConEscape(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setAbierta(false);
        botonRef.current?.focus();
      }
    }

    function cerrarFuera(evento: PointerEvent) {
      if (!contenedorRef.current?.contains(evento.target as Node)) {
        setAbierta(false);
      }
    }

    document.addEventListener('keydown', cerrarConEscape);
    document.addEventListener('pointerdown', cerrarFuera);
    return () => {
      document.removeEventListener('keydown', cerrarConEscape);
      document.removeEventListener('pointerdown', cerrarFuera);
    };
  }, [abierta]);

  return (
    <div className="campana" ref={contenedorRef}>
      <button
        ref={botonRef}
        type="button"
        className="campana__boton"
        aria-label={`${notificaciones.length} advertencias`}
        aria-expanded={abierta}
        aria-controls={idPanel}
        onClick={() => setAbierta((valor) => !valor)}
      >
        <span aria-hidden="true">🔔</span>
        <span className="campana__contador" aria-hidden="true">
          {notificaciones.length}
        </span>
      </button>

      {abierta && (
        <section id={idPanel} className="campana__panel" aria-label="Advertencias recientes">
          <h2>Advertencias</h2>
          {recientes.length === 0 ? (
            <p className="campana__vacio">No hay casos por revisar.</p>
          ) : (
            <ListaAdvertencias notificaciones={recientes} />
          )}
          <Link
            className="campana__todas"
            to="/profesora/inicio#advertencias"
            onClick={() => setAbierta(false)}
          >
            Ver todas
          </Link>
        </section>
      )}
    </div>
  );
}
