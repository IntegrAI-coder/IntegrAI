import { Link } from 'react-router-dom';
import type { NotificacionAdvertencia } from '../domain/tipos';

export function ListaAdvertencias({
  notificaciones,
}: {
  notificaciones: NotificacionAdvertencia[];
}) {
  return (
    <ol className="lista-advertencias">
      {notificaciones.map((notificacion) => (
        <li key={notificacion.idNotificacion} className="advertencia">
          <span className="advertencia__icono" aria-hidden="true">!</span>
          <span className="sr-only">Advertencia</span>
          <div className="advertencia__contenido">
            <p className="advertencia__titulo">{notificacion.titulo}</p>
            <p className="advertencia__detalle">{notificacion.detalle}</p>
            <div className="advertencia__pie">
              <time dateTime={notificacion.fecha}>{notificacion.fecha}</time>
              <Link to={notificacion.href}>Ver ficha</Link>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
