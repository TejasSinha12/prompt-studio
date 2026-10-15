"use client";

import { useState } from "react";
import { CATEGORY_LABELS, PROFILE_LABELS } from "@/lib/format";
import { Button, Field, Input, Select, Textarea } from "./ui";

export interface NewProjectValues {
  name: string;
  description: string;
  original_idea: string;
  task_category: string;
  target_agent: string;
}

export function validateProject(v: NewProjectValues): Partial<Record<keyof NewProjectValues, string>> {
  const errors: Partial<Record<keyof NewProjectValues, string>> = {};
  if (!v.name.trim()) errors.name = "Name is required.";
  else if (v.name.trim().length > 200) errors.name = "Name must be 200 characters or fewer.";
  if (v.description.length > 5000) errors.description = "Description must be 5000 characters or fewer.";
  if (v.original_idea.length > 100_000) errors.original_idea = "Idea must be 100,000 characters or fewer.";
  return errors;
}

export function ProjectForm({
  onSubmit,
  onCancel,
  busy,
  serverError,
  defaultAgent = "generic_coding",
}: {
  onSubmit: (v: NewProjectValues) => void;
  onCancel: () => void;
  busy?: boolean;
  serverError?: string | null;
  defaultAgent?: string;
}) {
  const [v, setV] = useState<NewProjectValues>({
    name: "",
    description: "",
    original_idea: "",
    task_category: "feature",
    target_agent: defaultAgent,
  });
  const [touched, setTouched] = useState(false);
  const errors = validateProject(v);
  const set = (k: keyof NewProjectValues) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (Object.keys(errors).length === 0) onSubmit({ ...v, name: v.name.trim() });
      }}
      className="flex flex-col gap-3"
    >
      <Field label="Name" error={touched ? errors.name : null}>
        {(id) => <Input id={id} value={v.name} onChange={set("name")} autoFocus maxLength={220} aria-invalid={Boolean(touched && errors.name)} />}
      </Field>
      <Field label="Rough idea (optional)" hint="Describe what you want in your own words. You can refine it later." error={touched ? errors.original_idea : null}>
        {(id) => <Textarea id={id} rows={5} value={v.original_idea} onChange={set("original_idea")} />}
      </Field>
      <Field label="Description (optional)" error={touched ? errors.description : null}>
        {(id) => <Input id={id} value={v.description} onChange={set("description")} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Task category">
          {(id) => (
            <Select id={id} value={v.task_category} onChange={set("task_category")}>
              {Object.entries(CATEGORY_LABELS).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Target agent">
          {(id) => (
            <Select id={id} value={v.target_agent} onChange={set("target_agent")}>
              {Object.entries(PROFILE_LABELS).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      {serverError && <p role="alert" className="text-xs text-danger">{serverError}</p>}
      <div className="flex justify-end gap-2 pt-1">
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="primary" busy={busy}>
          Create project
        </Button>
      </div>
    </form>
  );
}
