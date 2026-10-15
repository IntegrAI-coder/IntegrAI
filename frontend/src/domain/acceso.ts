import { claveCurso } from './consultas';
import type { CursoProfesora, Educadora, Nino, Profesora } from './tipos';

export function normalizarTelefono(telefono: string): string {
  return telefono.replace(/\D/g, '');
}

export function telefonosCoinciden(primero: string, segundo: string): boolean {
  const a = normalizarTelefono(primero);
  const b = normalizarTelefono(segundo);
  if (!a || !b) {
    return false;
  }
  if (a === b) {
    return true;
  }
  return a.length >= 9 && b.length >= 9 && a.slice(-9) === b.slice(-9);
}

export function telefonoDemo(idEducadora: string): string {
  const sufijo = idEducadora.replace(/\D/g, '').padStart(8, '0').slice(-8);
  return `569${sufijo}`;
}

export function asignarProfesorasDemo(
  educadoras: Educadora[],
  ninos: Nino[],
): Profesora[] {
  const salasPorJardin = new Map<string, string[]>();
  for (const nino of ninos) {
    const salas = salasPorJardin.get(nino.idJardin) ?? [];
    if (!salas.includes(nino.salaGrupo)) {
      salas.push(nino.salaGrupo);
      salasPorJardin.set(nino.idJardin, salas);
    }
  }
  for (const salas of salasPorJardin.values()) {
    salas.sort((a, b) => a.localeCompare(b));
  }

  const indicePorJardin = new Map<string, number>();
  return [...educadoras]
    .sort((a, b) => a.idEducadora.localeCompare(b.idEducadora))
    .map((educadora) => {
      const salas = salasPorJardin.get(educadora.idJardin) ?? [];
      const indice = indicePorJardin.get(educadora.idJardin) ?? 0;
      indicePorJardin.set(educadora.idJardin, indice + 1);
      const salaGrupo = salas.length > 0 ? salas[indice % salas.length] : undefined;
      return {
        idEducadora: educadora.idEducadora,
        telefono: telefonoDemo(educadora.idEducadora),
        cursos: salaGrupo
          ? [{ idJardin: educadora.idJardin, salaGrupo }]
          : [],
      };
    });
}

export function filtrarCursosDeProfesora<T extends CursoProfesora>(
  cursos: T[],
  profesora: Profesora,
): T[] {
  const permitidos = new Set(
    profesora.cursos.map((curso) => claveCurso(curso.idJardin, curso.salaGrupo)),
  );
  return cursos.filter((curso) => permitidos.has(claveCurso(curso.idJardin, curso.salaGrupo)));
}

export function tieneAccesoCurso(
  profesora: Profesora,
  idJardin: string,
  salaGrupo: string,
): boolean {
  const buscado = claveCurso(idJardin, salaGrupo);
  return profesora.cursos.some(
    (curso) => claveCurso(curso.idJardin, curso.salaGrupo) === buscado,
  );
}

export function tieneAccesoNino(profesora: Profesora, nino: Nino): boolean {
  return tieneAccesoCurso(profesora, nino.idJardin, nino.salaGrupo);
}
