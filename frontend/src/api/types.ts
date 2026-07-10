export interface TrajectoryPoint {
  step: number;
  value: number;
  lower: number | null;
  upper: number | null;
}

export interface Trajectory {
  points: TrajectoryPoint[];
  horizon_steps: number;
  confidence: number;
  generated_at: string;
}

export interface Constraint {
  id: string;
  type: string;
  bound: number;
  hard: boolean;
  justification_evidence_ids: string[];
  confidence: number;
  source: string;
}

export interface ObjectiveSpec {
  terms: string[];
  weights: number[];
  hard_constraint_ids: string[];
  soft_constraint_ids: string[];
  rationale: string;
}

export interface ActionStep {
  step_index: number;
  action_type: string;
  parameters: Record<string, unknown>;
  predicted_effect: Record<string, unknown>;
}

export interface ActionPlan {
  steps: ActionStep[];
  committed_step_index: number;
  horizon_steps: number;
}

export interface FalsificationResult {
  action_id: string;
  verdict: 'survives' | 'fails';
  failed_check: string | null;
  reasoning: string;
  evidence_ids: string[];
}

export interface LoopCycle {
  cycle_id: string;
  constraints_snapshot: Constraint[];
  trajectory: Trajectory;
  objective: ObjectiveSpec;
  action_plan: ActionPlan | null;
  falsification: FalsificationResult | null;
  committed: boolean;
  correlation_id: string;
}

export interface ChainEntry {
  entry_id: string;
  entry_type: string;
  correlation_id: string;
  content: Record<string, unknown>;
}

export interface SignalInput {
  metric: string;
  value: number;
  source?: string;
}

export interface CycleResponse {
  cycle_id: string;
  correlation_id: string;
  committed: boolean;
  action_type: string | null;
  falsification_verdict: string | null;
}

export interface ScenarioMeta {
  scenario: string;
  seed: number;
  total_steps: number;
  disturbance_step: number;
}
