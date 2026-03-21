/**
 * ATS optimization API client
 */

import { apiFetch, apiPost } from './client';

export interface ATSPlatform {
  value: 'workday' | 'taleo' | 'icims' | 'greenhouse' | 'lever' | 'successfactors' | 'auto';
  label: string;
}

export const ATS_PLATFORMS: ATSPlatform[] = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'workday', label: 'Workday' },
  { value: 'taleo', label: 'Taleo (Oracle)' },
  { value: 'icims', label: 'iCIMS' },
  { value: 'greenhouse', label: 'Greenhouse' },
  { value: 'lever', label: 'Lever' },
  { value: 'successfactors', label: 'SAP SuccessFactors' },
];

export interface PlatformDetection {
  platform: string;
  confidence: 'verified' | 'high' | 'medium' | 'low' | 'unknown';
  source: string;
  company_name?: string;
  job_url?: string;
}

export interface PlatformScore {
  platform: string;
  score: number;
  keyword_match: number;
  format_score: number;
  missing_keywords: string[];
  matched_keywords: string[];
  algorithm: string;
  strengths: string[];
  weaknesses: string[];
}

export interface MultiPlatformScores {
  target_platform: string;
  scores: Record<string, PlatformScore>;
  average_score: number;
  best_platform: string;
  worst_platform: string;
  all_platforms_above_threshold: boolean;
}

export interface RefinementIteration {
  iteration: number;
  prev_score: number;
  new_score: number;
  improvement: number;
  continued: boolean;
  reason: string;
}

export interface ATSOptimizationResult {
  resume_id: string;
  resume_data: any;
  target_platform: string;
  detected_platform?: PlatformDetection;
  initial_scores: MultiPlatformScores;
  final_scores: MultiPlatformScores;
  refinement_performed: boolean;
  refinement_iterations: RefinementIteration[];
  processing_time_seconds: number;
  recommendation: string;
}

export interface DetectPlatformRequest {
  job_description: string;
  job_url?: string;
  company_name?: string;
}

export interface DetectPlatformResponse {
  detection: PlatformDetection;
  suggested_platform: string;
  confidence_explanation: string;
}

export interface ScoreResumeRequest {
  resume_id?: string;
  resume_data?: any;
  job_description: string;
  platforms?: string[];
}

export interface ScoreResumeResponse {
  scores: MultiPlatformScores;
  generated_at: string;
}

export interface OptimizeResumeRequest {
  resume_id: string;
  job_description: string;
  job_url?: string;
  company_name?: string;
  target_platform?: string;
  language?: string;
  enable_cover_letter?: boolean;
  enable_outreach?: boolean;
  max_refinement_iterations?: number;
  score_threshold?: number;
}

export interface OptimizeResumeResponse {
  success: boolean;
  result?: ATSOptimizationResult;
  error?: string;
}

/**
 * Detect ATS platform from job description
 */
export async function detectATSPlatform(
  request: DetectPlatformRequest
): Promise<DetectPlatformResponse> {
  return apiPost('/ats/detect', request);
}

/**
 * Score resume against ATS platforms
 */
export async function scoreResume(
  request: ScoreResumeRequest
): Promise<ScoreResumeResponse> {
  return apiPost('/ats/score', request);
}

/**
 * Optimize resume for specific ATS platform
 */
export async function optimizeResumeForATS(
  request: OptimizeResumeRequest
): Promise<OptimizeResumeResponse> {
  return apiPost('/ats/optimize', request);
}
