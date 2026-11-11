import { api } from "../../../shared/api";
import type { AppConfig } from "../model/types";

export const getConfig = () => api<AppConfig>("/config");
