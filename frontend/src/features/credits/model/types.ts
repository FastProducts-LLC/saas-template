// Unions generated from the backend domain enums (scripts/gen_enums.py).
import type {
  CreditAction,
  CreditPack,
  ReservationStatus,
  TransactionType,
} from "../../../shared/api/enums";

export type { CreditAction, CreditPack, ReservationStatus, TransactionType };

export interface ActionCost {
  action: CreditAction;
  name: string;
  cost: number;
}

export interface Reservation {
  id: string;
  action: CreditAction;
  amount: number;
  status: ReservationStatus;
  reference: string | null;
  expires_at: string;
  created_at: string;
}

export interface Wallet {
  balance: number;
  reserved: number;
  monthly_allowance: number;
  allowance_period: string | null;
  pending_holds: Reservation[];
}

export interface CreditTransaction {
  id: string;
  type: TransactionType;
  action: CreditAction | null;
  amount: number;
  balance_after: number;
  description: string | null;
  user_email: string | null;
  api_key_name: string | null;
  reservation_status: ReservationStatus | null;
  created_at: string;
}

export interface CreditHistory {
  items: CreditTransaction[];
  total: number;
}

export interface UsageAction {
  action: CreditAction;
  count: number;
  credits: number;
}

export interface UsageActor {
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  credits: number;
  count: number;
  limit: number | null;
  actions: UsageAction[];
}

export interface CreditUsage {
  period: string;
  items: UsageActor[];
  total_actors: number;
  total_credits: number;
}

export interface MemberLimit {
  user_id: string;
  email: string | null;
  monthly_limit: number;
  used_this_period: number;
  updated_at: string;
}

export interface CreditPackSpec {
  pack: CreditPack;
  name: string;
  credits: number;
  price_cents: number;
  unit_price_cents: number;
  discount_pct: number;
  purchasable: boolean;
}
