import { describe, expect, it } from 'vitest';
import { allProjects, folder, home, projectOf, sameView } from './views';

describe('sameView', () => {
  it('tells folders apart by project, with My generations as its own folder', () => {
    expect(sameView(folder('prj_film'), folder('prj_film'))).toBe(true);
    expect(sameView(folder('prj_film'), folder('prj_mood'))).toBe(false);
    expect(sameView(folder(null), folder('prj_film'))).toBe(false);
    expect(sameView(folder(null), folder(null))).toBe(true);
  });

  it('matches the views that have no folder by name', () => {
    expect(sameView(home, { name: 'home' })).toBe(true);
    expect(sameView(home, allProjects)).toBe(false);
    expect(sameView(allProjects, folder(null))).toBe(false);
  });
});

describe('projectOf', () => {
  it('files into the open project, and nowhere from anywhere else', () => {
    expect(projectOf(folder('prj_film'))).toBe('prj_film');
    expect(projectOf(folder(null))).toBeNull();
    expect(projectOf(home)).toBeNull();
    expect(projectOf(allProjects)).toBeNull();
  });
});
