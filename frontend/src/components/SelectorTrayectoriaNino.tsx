import { useId, useState } from 'react';
import type { Datos } from '../data/cargar';
import type { Nino } from '../domain/tipos';
import { GraficoTrayectoriaNivel } from './GraficoTrayectoriaNivel';
import { Vacio } from './Estado';

interface Props {
  datos: Datos;
  /** Niños/as entre los que se puede elegir (ya acotados al alcance del rol). */
  ninos: Nino[];
  titulo: string;
}

/** Selector de niño/a con su gráfico de trayectoria debajo. */
export function SelectorTrayectoriaNino({ datos, ninos, titulo }: Props) {
  const idSelector = useId();
  const [elegido, setElegido] = useState<string | null>(null);

  if (ninos.length === 0) {
    return (
      <div className="selector-nino">
        <h3 className="seccion__titulo">{titulo}</h3>
        <Vacio mensaje="No hay niños/as en la selección actual." />
      </div>
    );
  }

  const ordenados = [...ninos].sort((a, b) => a.idNino.localeCompare(b.idNino));
  const activo =
    ordenados.find((n) => n.idNino === elegido)?.idNino ?? ordenados[0]?.idNino ?? '';

  return (
    <div className="selector-nino">
      <h3 className="seccion__titulo">{titulo}</h3>
      <div className="buscador">
        <label htmlFor={idSelector}>Niño o niña</label>
        <select id={idSelector} value={activo} onChange={(e) => setElegido(e.target.value)}>
          {ordenados.map((n) => (
            <option key={n.idNino} value={n.idNino}>
              {n.idNino}
            </option>
          ))}
        </select>
      </div>
      <GraficoTrayectoriaNivel datos={datos} idNino={activo} />
    </div>
  );
}
