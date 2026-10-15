/**
 * What the main area shows: the home screen, every folder (All projects), or one folder's gallery. A folder is a
 * project, or My generations (project null), which holds every generation, including those filed in projects.
 */
export type View = { name: 'home' } | { name: 'projects' } | { name: 'folder'; project: string | null };

export const home: View = { name: 'home' };
export const allProjects: View = { name: 'projects' };
export const folder = (project: string | null): View => ({ name: 'folder', project });

export function sameView(a: View, b: View) {
  return a.name === b.name && (a.name !== 'folder' || (b.name === 'folder' && a.project === b.project));
}

/** The project that generating from this view files into: the open project's, else none. */
export const projectOf = (view: View) => (view.name === 'folder' ? view.project : null);
