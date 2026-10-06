import type { components } from "@contracts/backend-ot";

type Schemas = components["schemas"];

export type Health = Schemas["HealthResponse"];
export type Site = Schemas["SiteResponse"];
