"use client";

import { useEffect, useState } from "react";

import { CheckIcon, ShieldIcon } from "@/components/icons";
import { apiRequest, type KnowledgeStatus as KnowledgeStatusType } from "@/lib/api";

export function KnowledgeStatus({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<KnowledgeStatusType | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    apiRequest<KnowledgeStatusType>("/api/v1/knowledge/status", {}, 8_000)
      .then(setStatus)
      .catch(() => setUnavailable(true));
  }, []);

  if (compact) {
    return (
      <span className={status?.ready ? "live-pill ready" : "live-pill"}>
        <span className="live-dot" />
        {status?.ready
          ? `Dữ liệu ${status.academic_year || "đã xác minh"}`
          : unavailable ? "Backend chưa kết nối" : "Đang kiểm tra dữ liệu"}
      </span>
    );
  }

  return (
    <div className="knowledge-card">
      <span className="knowledge-icon"><ShieldIcon /></span>
      <div>
        <span className="eyebrow">Tình trạng kho tri thức</span>
        <strong>{status?.ready ? "Sẵn sàng và có kiểm soát nguồn" : unavailable ? "Chưa kết nối backend" : "Đang kiểm tra…"}</strong>
        <p>
          {status?.ready
            ? `${status.sources} nguồn chính thức · ${status.documents} tài liệu${status.verified_as_of ? ` · kiểm chứng ${status.verified_as_of}` : ""}`
            : "Frontend sẽ không tự tạo câu trả lời khi backend chưa sẵn sàng."}
        </p>
      </div>
      {status?.ready ? <CheckIcon className="knowledge-check" /> : null}
    </div>
  );
}
