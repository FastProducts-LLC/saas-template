export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  is_superuser: boolean;
  marketing_opt_in: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  refresh_token: string | null;
  user: User;
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
