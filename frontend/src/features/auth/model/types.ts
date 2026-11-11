export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  is_superuser: boolean;
  marketing_opt_in: boolean;
  /** True when the user turned off product analytics for their account. */
  analytics_opt_out: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface RegisterPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  password_confirmation: string;
  terms_accepted: boolean;
  marketing_opt_in: boolean;
}

export interface SessionResponse {
  access_token: string;
  user: User;
}
