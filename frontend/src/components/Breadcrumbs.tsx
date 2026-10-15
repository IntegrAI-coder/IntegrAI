import { Link } from 'react-router-dom';

export interface Miga {
  etiqueta: string;
  ruta?: string;
}

export function Breadcrumbs({ migas }: { migas: Miga[] }) {
  return (
    <nav className="breadcrumbs" aria-label="Ruta de navegación">
      <ol>
        {migas.map((miga, indice) => {
          const esActual = indice === migas.length - 1;
          return (
            <li key={miga.etiqueta} aria-current={esActual ? 'page' : undefined}>
              {miga.ruta && !esActual ? (
                <Link to={miga.ruta}>{miga.etiqueta}</Link>
              ) : (
                miga.etiqueta
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
