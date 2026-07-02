"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/EmptyState";
import { ExperimentTable } from "@/components/tables/ExperimentTable";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Experiment } from "@/types/api";

export default function ExperimentsPage() {
  const router = useRouter();
  const { data } = useApi<Experiment[]>("/api/experiments", []);
  const [localData, setLocalData] = useState<Experiment[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [selectedExperimentIds, setSelectedExperimentIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const experiments = localData ?? data;

  function experimentDetailPath(row: Experiment) {
    const id = encodeURIComponent(row.experiment_id);
    return row.strategy === "PHASE1" ? `/phase1?experiment=${id}` : `/backtest?experiment=${id}`;
  }

  function toggleExperiment(experimentId: string) {
    setSelectedExperimentIds((current) => {
      const next = new Set(current);
      if (next.has(experimentId)) {
        next.delete(experimentId);
      } else {
        next.add(experimentId);
      }
      return next;
    });
  }

  function clearSelection() {
    setSelectedExperimentIds(new Set());
  }

  async function deleteSelectedExperiments() {
    const experimentIds = Array.from(selectedExperimentIds);
    if (experimentIds.length === 0) {
      return;
    }
    const confirmed = window.confirm(
      `确认删除 ${experimentIds.length} 个实验？会同步删除关联交易、孤儿信号和报告文件。`
    );
    if (!confirmed) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      const response = await fetch("/api/experiments", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ experiment_ids: experimentIds, delete_artifacts: true })
      });
      if (!response.ok) {
        throw new Error(`delete_failed:${response.status}`);
      }
      setLocalData(experiments.filter((experiment) => !selectedExperimentIds.has(experiment.experiment_id)));
      clearSelection();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "delete_failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-4xl font-semibold">实验</h2>
          <p className="mt-2 text-sm text-muted">
            先比较配置哈希、成本压力、交易数和拒绝原因，再判断回测是否可信。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button
                className="bg-surface2 text-text hover:bg-border"
                onClick={() => setSelectedExperimentIds(new Set(experiments.map((item) => item.experiment_id)))}
              >
                全选
              </Button>
              <Button className="bg-surface2 text-text hover:bg-border" onClick={clearSelection}>
                清空
              </Button>
              <Button
                className="bg-negative text-white hover:bg-negative/80 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={deleteSelectedExperiments}
                disabled={selectedExperimentIds.size === 0 || deleting}
              >
                {deleting ? "删除中..." : `删除所选 ${selectedExperimentIds.size}`}
              </Button>
            </>
          ) : null}
          <Button
            className={editing ? "bg-surface2 text-text hover:bg-border" : undefined}
            onClick={() => {
              setEditing((value) => !value);
              clearSelection();
              setDeleteError(null);
            }}
          >
            {editing ? "完成" : "编辑"}
          </Button>
        </div>
      </div>
      <Card className="p-5">
        {deleteError ? (
          <div className="mb-4 rounded-lg border border-negative/40 bg-negative/10 p-3 text-sm text-negative">
            删除失败：{deleteError}
          </div>
        ) : null}
        {experiments.length === 0 ? (
          <EmptyState title="暂无实验运行" description="先跑流水线，实验表会自动读取 SQLite 中的最新结果。" />
        ) : (
          <ExperimentTable
            data={experiments}
            onRowClick={(row) => router.push(experimentDetailPath(row))}
            editing={editing}
            selectedExperimentIds={selectedExperimentIds}
            onToggleExperiment={toggleExperiment}
          />
        )}
      </Card>
    </div>
  );
}
