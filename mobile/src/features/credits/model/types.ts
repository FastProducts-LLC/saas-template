// Unions generated from the backend domain enums (scripts/gen_enums.py).
import type {
  CreditAction,
  ReservationStatus,
  TransactionType,
} from "../../../shared/api/enums";

export type { CreditAction, ReservationStatus, TransactionType };

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
