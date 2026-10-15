import { describe, expect, it } from 'vitest';
import { parsearUrlRepo } from './repos';

describe('parsearUrlRepo', () => {
  it('acepta el atajo owner/repo', () => {
    expect(parsearUrlRepo('acme/demo')).toEqual({
      owner: 'acme',
      repo: 'demo',
      url: 'https://github.com/acme/demo',
    });
  });

  it('acepta URL https y quita el .git', () => {
    expect(parsearUrlRepo('https://github.com/acme/demo.git')).toEqual({
      owner: 'acme',
      repo: 'demo',
      url: 'https://github.com/acme/demo',
    });
  });

  it('rechaza esquemas, hosts y formatos inválidos', () => {
    for (const entrada of [
      '',
      'http://github.com/acme/demo',
      'git://github.com/acme/demo',
      'https://evil.example.com/acme/demo',
      'https://github.com/acme',
      'https://github.com/acme/demo/extra',
      'https://github.com/../etc',
      'https://github.com/acme/..',
    ]) {
      expect(parsearUrlRepo(entrada)).toBeNull();
    }
  });
});
