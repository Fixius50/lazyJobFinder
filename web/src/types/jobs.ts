export interface JobListItem {
  id: number;
  title: string;
  company: string;
  location: string;
  is_remote: number;
  source: string;
  canonical_url: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string;
  date_posted?: string;
  created_at: string;
  updated_at: string;
  status: string;
  duplicate_of_id?: number | null;
  similarity_score?: number | null;
  alternate_sources?: string;
  telegram_notified: number;
  ui_saved: number;
  score?: number | null;
  fit_level?: string | null;
  should_apply?: number | null;
  has_cv: boolean;
  has_letter: boolean;
}

export interface PaginatedJobsResponse {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobDetail extends JobListItem {
  description?: string;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  gaps: string[];
  reasoning?: string;
  diff_summary?: string;
  cv_pdf_path?: string;
  cv_md_path?: string;
  letter_pdf_path?: string;
  letter_md_path?: string;
  evaluated_at?: string;
  documents_generated_at?: string;
}

export interface JobFilterParams {
  search?: string;
  source?: string;
  status?: string;
  min_score?: number;
  is_remote?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: string;
}
