import type { ComparisonOperator } from "@/shared/components/conditions/conditionModel";
import type { Operator } from "../types";

// The alarm rule builder uses the shared condition editor; these map its operators onto the alarm model.

export const ALARM_OPERATORS: ComparisonOperator[] = [">", "<", ">=", "<=", "==", "!="];

export const toConditionOperator = (operator: Operator): ComparisonOperator => (operator === "=" ? "==" : operator);

export const toAlarmOperator = (operator: ComparisonOperator): Operator => (operator === "==" ? "=" : operator);
