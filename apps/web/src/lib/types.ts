// The shapes the API sends and takes. They're generated from its OpenAPI schema into api-types.ts (pnpm api:types), so
// they can't drift from it. Field names are snake_case to match the JSON on the wire.

import type { components } from './api-types';

type Schemas = components['schemas'];

export type MediaType = Schemas['MediaType'];
export type Capability = Schemas['Capability'];
/** What an attached asset is for. The output type plus the roles of the inputs decide the capability. */
export type InputRole = Schemas['InputRole'];
export type GenerationStatus = Schemas['GenerationStatus'];
export type AspectRatio = Schemas['Params']['aspect_ratio'];

export type Asset = Schemas['AssetOut'];
export type Generation = Schemas['GenerationOut'];
export type GenerationInput = Schemas['GenerationInputOut'];
/** The body of a generate request: no workflow, just the inputs and their roles, and optionally a model. */
export type GenerationRequest = Schemas['GenerationIn'];
/** A workflow as the composer sees it: its capability, its model and the settings it offers. */
export type Workflow = Schemas['WorkflowOut'];
/**
 * A folder the user made, with its newest outputs as covers. My generations isn't one: it holds every generation,
 * and one made in a project is in both.
 */
export type Project = Schemas['ProjectOut'];
