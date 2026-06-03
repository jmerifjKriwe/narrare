/**
 * Narrare API client.
 *
 * Typed wrappers around all API endpoints.
 * Components never call fetch directly — always use these functions.
 *
 * This file is a compatibility re-export. New code should import directly
 * from domain files (e.g. "@/lib/api/novels") or from the barrel index:
 *   import { novelsApi } from "@/lib/api";
 *
 * Access token is stored in memory (not localStorage).
 * Refresh token is in an httpOnly cookie (set by server).
 */

export * from "./index";
