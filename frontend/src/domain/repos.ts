export interface UrlRepo {
  owner: string;
  repo: string;
  url: string;
}

const COMPONENTE = /^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$/;
const HOST = 'github.com';

/**
 * Valida y normaliza una referencia de repositorio en el cliente (espejo de la
 * validación del backend). Acepta `owner/repo` o `https://github.com/owner/repo`.
 * Devuelve `null` si no es válida.
 */
export function parsearUrlRepo(entrada: string): UrlRepo | null {
  const texto = entrada.trim();
  if (!texto) {
    return null;
  }

  let resto: string;
  if (texto.includes('://')) {
    if (!texto.toLowerCase().startsWith('https://')) {
      return null;
    }
    resto = texto.slice('https://'.length);
  } else {
    resto = `${HOST}/${texto}`;
  }

  const partes = resto.split('/').filter(Boolean);
  if (partes.length !== 3) {
    return null;
  }
  const [host, owner, repoBruto] = partes;
  if (host === undefined || owner === undefined || repoBruto === undefined) {
    return null;
  }
  if (host.toLowerCase() !== HOST) {
    return null;
  }

  const repo = repoBruto.endsWith('.git') ? repoBruto.slice(0, -4) : repoBruto;
  if (!COMPONENTE.test(owner) || !COMPONENTE.test(repo)) {
    return null;
  }
  return { owner, repo, url: `https://${HOST}/${owner}/${repo}` };
}
