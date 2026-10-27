export type EmployeeStatus = "active" | "inactive" | "suspended";

export interface Employee {
  id: string;
  code: string;
  full_name: string;
  department?: string | null;
  position?: string | null;
  email?: string | null;
  phone?: string | null;
  status: EmployeeStatus;
  photo_url?: string | null;
  hired_at?: string | null;
  created_at: string;
}

export type CredentialType = "face" | "fingerprint";

export interface AccessCredential {
  id: string;
  employee_id: string;
  type: CredentialType;
  is_active: boolean;
  enrolled_at: string;
}

export type AccessResult = "accepted" | "rejected" | "unknown";

export interface AccessPolicy {
  id: string;
  employee_id: string;
  access_point_id: string;
  allowed_days: string[];
  allowed_time_start: string;
  allowed_time_end: string;
  is_active: boolean;
  created_at: string;
}

export interface AccessLogRow {
  id: string;
  method: CredentialType;
  result: AccessResult;
  confidence: number | null;
  timestamp: string;
  employees: { code: string; full_name: string } | null;
}
