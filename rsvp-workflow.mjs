export const WORKFLOW_VERSION = "2026-08-plan-scheduled-v2-budget-review";

const PLAN_REVIEW_STATUSES = new Set(["pending", "approved", "rejected"]);

export function workflowStage(record = {}) {
  return record?.workflowStage === "plan" ? "plan" : "scheduled";
}

export function normalizeReviewStatus(value) {
  return PLAN_REVIEW_STATUSES.has(value) ? value : "pending";
}

export function isPlanRecord(record) {
  return workflowStage(record) === "plan";
}

export function isScheduledRecord(record) {
  return workflowStage(record) === "scheduled";
}

export function withWorkflow(record = {}) {
  if (!record || typeof record !== "object") return record;
  const stage = workflowStage(record);
  if (stage === "plan") {
    return {
      ...record,
      workflowVersion: WORKFLOW_VERSION,
      workflowStage: "plan",
      reviewStatus: normalizeReviewStatus(record.reviewStatus)
    };
  }
  return {
    ...record,
    workflowVersion: record.workflowVersion || WORKFLOW_VERSION,
    workflowStage: "scheduled"
  };
}

export function canSchedulePlan(record) {
  return isPlanRecord(record) && normalizeReviewStatus(record?.reviewStatus) === "approved";
}

export function activePlanDuplicateKey(record, creatorKey = "") {
  if (!isPlanRecord(record) || !creatorKey) return "";
  const reviewStatus = normalizeReviewStatus(record?.reviewStatus);
  if (reviewStatus === "rejected") return "";
  return `plan:${creatorKey}`;
}

export function reviewStatusLabel(value) {
  const status = normalizeReviewStatus(value);
  if (status === "approved") return "已批准";
  if (status === "rejected") return "不邀请";
  return "待审核";
}

export function planFeeNumber(record = {}) {
  if (record?.visitType !== "付费探店") return 0;
  const match = String(record?.feeAmount || "").replace(/,/g, "").match(/(\d+(?:\.\d{1,2})?)/);
  const value = match ? Number(match[1]) : 0;
  return Number.isFinite(value) && value > 0 ? value : 0;
}

export function planPricingError(record = {}) {
  if (!isPlanRecord(record)) return "";
  if (!record.visitType) return "请选择这位候选是免费博主还是付费博主。";
  if (record.visitType === "付费探店" && planFeeNumber(record) <= 0) {
    return "付费博主必须填写有效价钱。";
  }
  return "";
}

export function validateWorkflowTransition(existingRecord, incomingRecord) {
  const incoming = withWorkflow(incomingRecord || {});
  const existing = existingRecord ? withWorkflow(existingRecord) : null;
  const planPricingChanged = existing && isPlanRecord(existing) && isPlanRecord(incoming)
    ? incoming.visitType !== existing.visitType || String(incoming.feeAmount || "") !== String(existing.feeAmount || "")
    : false;
  const isBeingApproved = existing && isPlanRecord(existing) && isPlanRecord(incoming)
    ? normalizeReviewStatus(existing.reviewStatus) !== "approved" && normalizeReviewStatus(incoming.reviewStatus) === "approved"
    : false;
  if (isPlanRecord(incoming) && (!existing || planPricingChanged || isBeingApproved)) {
    const incomingPricingError = planPricingError(incoming);
    if (incomingPricingError) return incomingPricingError;
  }
  if (!existing) {
    if (isScheduledRecord(incoming) && incoming.type !== "post") {
      return "新预约必须先加入 Plan，并由店长批准后才能进入 Scheduled。";
    }
    if (isPlanRecord(incoming) && (incoming.dateISO || incoming.timeText)) {
      return "Plan 候选阶段不能填写预约日期或时间。";
    }
    return "";
  }
  if (isScheduledRecord(existing) && isPlanRecord(incoming)) {
    return "Scheduled 记录不能退回为新的 Plan 候选。";
  }
  if (isPlanRecord(existing) && isScheduledRecord(incoming)) {
    const existingPricingError = planPricingError(existing);
    if (existingPricingError) return existingPricingError;
    if (normalizeReviewStatus(existing.reviewStatus) !== "approved") {
      return "这位博主还没有获得店长批准，不能进入 Scheduled。";
    }
    if (!incoming.dateISO || !incoming.timeText) {
      return "请填写完整的预约日期和时间，才能进入 Scheduled。";
    }
    if (incoming.visitType !== existing.visitType || planFeeNumber(incoming) !== planFeeNumber(existing)) {
      return "预约时不能修改店长已经批准的免费/付费类型或价钱；如需改价，请先重新审核。";
    }
  }
  return "";
}
