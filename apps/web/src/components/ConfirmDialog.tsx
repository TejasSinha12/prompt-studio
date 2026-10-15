"use client";

import { useEffect, useState } from "react";
import { Button, Dialog, Input } from "./ui";

/** Confirmation for destructive actions. If `phrase` is set, the user must type it. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  phrase,
  busy = false,
  danger = true,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  phrase?: string;
  busy?: boolean;
  danger?: boolean;
}) {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);
  const ok = !phrase || typed === phrase;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant={danger ? "danger" : "primary"} disabled={!ok} busy={busy} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-[13px]">
        <div>{message}</div>
        {phrase && (
          <label className="flex flex-col gap-1 text-xs text-muted">
            Type <code className="font-mono text-text">{phrase}</code> to confirm
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus aria-label={`Type ${phrase} to confirm`} />
          </label>
        )}
      </div>
    </Dialog>
  );
}
