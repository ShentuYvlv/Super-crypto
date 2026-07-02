"use client";

import Link from "next/link";
import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { HashBadge } from "@/components/HashBadge";
import { MetricCard } from "@/components/MetricCard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { displayDateTime, displayStatus, displayText } from "@/lib/display";
import type {
  Phase1ExperimentDetail,
  Phase1ExperimentSummary,
  Phase1FeatureQuality,
  Phase1ModelResult,
  Phase1SplitSummary,
  Phase1WindowDiagnostic
} from "@/types/api";

const EMPTY_SUMMARY: Phase1ExperimentSummary = {
  experiment_id: "",
  status: "not_run",
  label_count: 0,
  sample_count: 0,
  positive_sample_count: 0,
  negative_sample_count: 0,
  train_sample_count: 0,
  train_positive_count: 0,
  holdout_sample_count: 0,
  holdout_positive_count: 0,
  train_f1: 0,
  holdout_f1: 0,
  holdout_precision: 0,
  holdout_recall: 0,
  lightgbm_holdout_f1: null
};

const EMPTY_DETAIL: Phase1ExperimentDetail = {
  experiment: {
    experiment_id: "",
    name: "phase1_prediction",
    strategy: "PHASE1",
    engine: "classification",
    split: "",
    status: "not_run",
    config_hash: "",
    split_hash: "",
    data_snapshot_hash: "",
    git_commit_hash: "",
    report_path: "",
    trade_log_path: "",
    created_at: "",
    metrics: {
      net_return: 0,
      sharpe: 0,
      sortino: 0,
      max_drawdown: 0,
      profit_factor: 0,
      win_rate: 0,
      avg_win: 0,
      avg_loss: 0,
      trade_count: 0,
      median_holding_minutes: 0,
      fee_cost: 0,
      slippage_cost: 0,
      funding_cost: 0,
      top5_removed_net_return: 0
    }
  },
  summary: EMPTY_SUMMARY,
  splits: [],
  windows: [],
  labels: [],
  samples: [],
  sample_limit: 500,
  sample_count: 0,
  candidates: [],
  feature_quality: [],
  model_results: [],
  conclusion_flags: [],
  report_urls: {},
  artifact_paths: {}
};

const MODEL_LABELS: Record<string, string> = {
  fr_baseline: "资金费率基线",
  fr_oi: "资金费率 + OI",
  fr_oi_liquidation: "资金费率 + OI + 爆仓",
  fr_oi_liquidation_taker: "资金费率 + OI + 爆仓 + 主动买卖",
  all_available_features: "全部可用特征",
  lightgbm_all_features: "LightGBM 全特征"
};

function pct(value: number | null | undefined, digits = 1) {
  return `${((value ?? 0) * 100).toFixed(digits)}%`;
}

function numberText(value: unknown, digits = 6) {
  if (value == null || value === "") {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  if (Math.abs(parsed) >= 1) {
    return parsed.toFixed(3);
  }
  return parsed.toFixed(digits);
}

function toneForStatus(status: string): "positive" | "warning" | "negative" | "accent" {
  if (status === "healthy" || status === "covered" || status === "completed") {
    return "positive";
  }
  if (status === "missing" || status === "failed" || status === "danger") {
    return "negative";
  }
  if (status === "partial" || status === "warning") {
    return "warning";
  }
  return "accent";
}

function MetricHelp() {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">字段说明</h3>
      <div className="mt-4 grid gap-4 text-sm leading-6 text-muted md:grid-cols-3">
        <p>标签：一次自动识别出的拉盘事件，包含开始、峰值和下跌结束时间。</p>
        <p>正样本：事件开始前 N 小时的特征快照；负样本：远离事件的普通时间点。</p>
        <p>F1：精确率和召回率的综合分数；holdout 结果比训练集更重要。</p>
      </div>
    </Card>
  );
}

function SplitTable({ rows }: { rows: Phase1SplitSummary[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">Split 分布</h3>
      <p className="mt-1 text-sm text-muted">训练集用于调阈值或训练模型；留出集只用于最终检验。</p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">分组</th>
              <th className="py-2 pr-4">代币</th>
              <th className="py-2 pr-4">标签</th>
              <th className="py-2 pr-4">样本</th>
              <th className="py-2 pr-4">正样本</th>
              <th className="py-2 pr-4">负样本</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.split} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">{displayText(row.split)}</td>
                <td className="py-3 pr-4 text-muted">{row.symbols.join("、") || "-"}</td>
                <td className="py-3 pr-4">{row.label_count}</td>
                <td className="py-3 pr-4">{row.sample_count}</td>
                <td className="py-3 pr-4">{row.positive_sample_count}</td>
                <td className="py-3 pr-4">{row.negative_sample_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <EmptyState title="暂无 split 数据" description="该实验没有可读样本。" /> : null}
      </div>
    </Card>
  );
}

function WindowTable({ rows }: { rows: Phase1WindowDiagnostic[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">事件窗口与自动识别</h3>
      <p className="mt-1 text-sm text-muted">
        `event_start / peak / dump_end` 是程序在你配置的窗口内自动识别，不是人工真值。
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[1200px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">代币</th>
              <th className="py-2 pr-4">分组</th>
              <th className="py-2 pr-4">窗口</th>
              <th className="py-2 pr-4">事件开始</th>
              <th className="py-2 pr-4">峰值</th>
              <th className="py-2 pr-4">下跌结束</th>
              <th className="py-2 pr-4">正样本时间</th>
              <th className="py-2 pr-4">规则</th>
              <th className="py-2 pr-4">状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.symbol}-${row.window_id ?? row.window_start}`} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">{row.symbol}</td>
                <td className="py-3 pr-4">{displayText(row.split)}</td>
                <td className="py-3 pr-4 text-xs text-muted">
                  {displayDateTime(row.window_start)} 至 {displayDateTime(row.window_end)}
                  <br />
                  K线 {row.window_rows}
                </td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.detected_event_start)}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.peak_time)}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.dump_end)}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.positive_sample_time)}</td>
                <td className="py-3 pr-4 text-muted">{row.detection_rule ?? "-"}</td>
                <td className="py-3 pr-4">
                  <Badge tone={toneForStatus(row.status)}>{displayText(row.status)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <EmptyState title="暂无事件窗口" description="该实验没有窗口诊断。" /> : null}
      </div>
    </Card>
  );
}

function ModelTable({ rows }: { rows: Phase1ModelResult[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">阈值规则与 LightGBM</h3>
      <p className="mt-1 text-sm text-muted">
        阈值规则在训练集上找最佳阈值；LightGBM 是二分类模型。两者都必须看 holdout。
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[1050px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">实验</th>
              <th className="py-2 pr-4">模型</th>
              <th className="py-2 pr-4">训练F1</th>
              <th className="py-2 pr-4">留出F1</th>
              <th className="py-2 pr-4">训练精确/召回</th>
              <th className="py-2 pr-4">留出精确/召回</th>
              <th className="py-2 pr-4">阈值</th>
              <th className="py-2 pr-4">状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.experiment} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">
                  {MODEL_LABELS[row.experiment] ?? row.experiment}
                </td>
                <td className="py-3 pr-4">{row.model === "lightgbm" ? "LightGBM" : "阈值规则"}</td>
                <td className="py-3 pr-4">{pct(row.train_f1)}</td>
                <td className="py-3 pr-4">{pct(row.holdout_f1)}</td>
                <td className="py-3 pr-4">{pct(row.train_precision, 0)} / {pct(row.train_recall, 0)}</td>
                <td className="py-3 pr-4">{pct(row.holdout_precision, 0)} / {pct(row.holdout_recall, 0)}</td>
                <td className="py-3 pr-4">{numberText(row.threshold)}</td>
                <td className="py-3 pr-4">
                  <Badge tone={toneForStatus(row.status)}>{displayStatus(row.status)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function FeatureQualityTable({ rows }: { rows: Phase1FeatureQuality[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">特征数据真实性</h3>
      <p className="mt-1 text-sm text-muted">
        这里区分“模型配置里有这个特征”和“本次样本里真的有数据”。
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">特征</th>
              <th className="py-2 pr-4">状态</th>
              <th className="py-2 pr-4">非零样本</th>
              <th className="py-2 pr-4">缺失比例</th>
              <th className="py-2 pr-4">可用列</th>
              <th className="py-2 pr-4">质量计数</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">{row.label}</td>
                <td className="py-3 pr-4">
                  <Badge tone={toneForStatus(row.status)}>{displayText(row.status)}</Badge>
                </td>
                <td className="py-3 pr-4">{row.nonzero_sample_count} / {row.sample_count}</td>
                <td className="py-3 pr-4">{pct(row.missing_ratio, 0)}</td>
                <td className="py-3 pr-4 text-xs text-muted">{row.available_columns.join(", ") || "-"}</td>
                <td className="py-3 pr-4 text-xs text-muted">
                  {Object.keys(row.quality_counts).length ? JSON.stringify(row.quality_counts) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function LabelsAndSamples({ detail }: { detail: Phase1ExperimentDetail }) {
  const sampleRows = detail.samples.slice(0, 120);
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card className="p-5">
        <h3 className="text-2xl font-semibold">生成标签</h3>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 pr-4">事件</th>
                <th className="py-2 pr-4">代币</th>
                <th className="py-2 pr-4">分组</th>
                <th className="py-2 pr-4">开始</th>
                <th className="py-2 pr-4">峰值</th>
                <th className="py-2 pr-4">结束</th>
              </tr>
            </thead>
            <tbody>
              {detail.labels.map((row) => (
                <tr key={`${row.event_id}-${row.symbol}`} className="border-t border-border">
                  <td className="py-3 pr-4">{String(row.event_id ?? "-")}</td>
                  <td className="py-3 pr-4 font-semibold">{String(row.symbol ?? "-")}</td>
                  <td className="py-3 pr-4">{displayText(String(row.split ?? ""))}</td>
                  <td className="py-3 pr-4 text-xs">{displayDateTime(String(row.event_start ?? ""))}</td>
                  <td className="py-3 pr-4 text-xs">{displayDateTime(String(row.peak_time ?? ""))}</td>
                  <td className="py-3 pr-4 text-xs">{displayDateTime(String(row.dump_end ?? ""))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="p-5">
        <h3 className="text-2xl font-semibold">样本快照</h3>
        <p className="mt-1 text-sm text-muted">展示前 120 行；完整样本在 artifacts 路径里。</p>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 pr-4">代币</th>
                <th className="py-2 pr-4">分组</th>
                <th className="py-2 pr-4">标签</th>
                <th className="py-2 pr-4">样本时间</th>
                <th className="py-2 pr-4">FR</th>
                <th className="py-2 pr-4">OI 1h</th>
                <th className="py-2 pr-4">主动买比</th>
                <th className="py-2 pr-4">爆仓质量</th>
              </tr>
            </thead>
            <tbody>
              {sampleRows.map((row, index) => (
                <tr key={`${row.sample_id ?? index}`} className="border-t border-border">
                  <td className="py-3 pr-4 font-semibold">{String(row.symbol ?? "-")}</td>
                  <td className="py-3 pr-4">{displayText(String(row.split ?? ""))}</td>
                  <td className="py-3 pr-4">{Number(row.label ?? 0) === 1 ? "正样本" : "负样本"}</td>
                  <td className="py-3 pr-4 text-xs">{displayDateTime(String(row.sample_time ?? ""))}</td>
                  <td className="py-3 pr-4">{numberText(row.funding_rate)}</td>
                  <td className="py-3 pr-4">{numberText(row.oi_change_1h)}</td>
                  <td className="py-3 pr-4">{numberText(row.taker_buy_ratio, 3)}</td>
                  <td className="py-3 pr-4">{displayText(String(row.liquidation_data_quality ?? ""))}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sampleRows.length === 0 ? <EmptyState title="暂无样本" description="该实验没有可读样本。" /> : null}
        </div>
      </Card>
    </div>
  );
}

function Phase1Content() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experiments = useApi<Phase1ExperimentSummary[]>("/api/phase1/experiments", []);
  const selectedId = useMemo(
    () => searchParams.get("experiment") ?? experiments.data[0]?.experiment_id ?? "",
    [experiments.data, searchParams]
  );
  const detail = useApi<Phase1ExperimentDetail>(
    selectedId ? `/api/phase1/experiments/${encodeURIComponent(selectedId)}` : "/api/phase1/experiments/__none__",
    EMPTY_DETAIL
  );
  const data = detail.data.summary.experiment_id === selectedId ? detail.data : EMPTY_DETAIL;
  const summary = data.summary;
  const lightgbm = data.model_results.find((row) => row.model === "lightgbm");

  if (experiments.error) {
    return <ErrorState title="预测实验接口不可用" description="请检查 report server 是否已启动。" />;
  }

  if (experiments.data.length === 0) {
    return <EmptyState title="暂无预测实验" description="先运行 Phase1，页面会自动读取预测实验结果。" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-4xl font-semibold">预测实验</h2>
          <p className="mt-2 text-sm text-muted">
            Phase1 用来验证“拉盘前兆能否预测”，不是交易回测；核心看 holdout。
          </p>
        </div>
        <select
          value={selectedId}
          onChange={(event) => router.push(`/phase1?experiment=${encodeURIComponent(event.target.value)}`)}
          className="rounded-md border border-border bg-surface2 px-3 py-2 text-sm text-text"
        >
          {experiments.data.map((item) => (
            <option key={item.experiment_id} value={item.experiment_id}>
              {item.experiment_id} · {displayDateTime(item.created_at)}
            </option>
          ))}
        </select>
      </div>

      <Card className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <HashBadge value={selectedId || "-"} />
              <Badge tone={toneForStatus(summary.status)}>{displayStatus(summary.status)}</Badge>
              <span className="text-sm text-muted">{displayDateTime(summary.created_at)}</span>
            </div>
            <p className="text-sm text-muted">
              报告：{data.report_urls.html ? <Link className="text-accent" href={data.report_urls.html}>HTML</Link> : "-"}
              <span className="mx-2">/</span>
              {data.report_urls.markdown ? <Link className="text-accent" href={data.report_urls.markdown}>Markdown</Link> : "-"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.conclusion_flags.map((flag) => (
              <Badge key={flag.key} tone={flag.severity === "danger" ? "negative" : "warning"}>
                {flag.label}
              </Badge>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-6">
        <MetricCard label="标签" value={String(summary.label_count)} sublabel="自动识别事件" badge="Phase1" />
        <MetricCard label="样本" value={String(summary.sample_count)} sublabel={`${summary.positive_sample_count} 正 / ${summary.negative_sample_count} 负`} badge="分类" />
        <MetricCard label="训练F1" value={pct(summary.train_f1)} sublabel="训练+验证" badge="训练" />
        <MetricCard label="留出F1" value={pct(summary.holdout_f1)} sublabel={`${pct(summary.holdout_precision, 0)} 精确 / ${pct(summary.holdout_recall, 0)} 召回`} badge="holdout" />
        <MetricCard label="LightGBM 留出F1" value={pct(lightgbm?.holdout_f1 ?? summary.lightgbm_holdout_f1)} sublabel="二分类模型" badge="ML" />
        <MetricCard label="留出正样本" value={String(summary.holdout_positive_count)} sublabel={`${summary.holdout_sample_count} 个留出样本`} badge="验收" />
      </div>

      <MetricHelp />
      <SplitTable rows={data.splits} />
      <WindowTable rows={data.windows} />
      <ModelTable rows={data.model_results} />
      <FeatureQualityTable rows={data.feature_quality} />
      <Card className="p-5">
        <h3 className="text-2xl font-semibold">Holdout 结论</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg bg-[#11161d] p-4">
            <p className="text-sm text-muted">留出 F1</p>
            <p className="mt-2 text-3xl font-semibold">{pct(summary.holdout_f1)}</p>
          </div>
          <div className="rounded-lg bg-[#11161d] p-4">
            <p className="text-sm text-muted">留出精确率</p>
            <p className="mt-2 text-3xl font-semibold">{pct(summary.holdout_precision)}</p>
          </div>
          <div className="rounded-lg bg-[#11161d] p-4">
            <p className="text-sm text-muted">留出召回率</p>
            <p className="mt-2 text-3xl font-semibold">{pct(summary.holdout_recall)}</p>
          </div>
        </div>
        <div className="mt-5 space-y-3">
          {data.conclusion_flags.map((flag) => (
            <div key={flag.key} className="rounded-lg border border-border bg-[#11161d] p-4">
              <div className="flex items-center gap-2">
                <Badge tone={flag.severity === "danger" ? "negative" : "warning"}>{flag.label}</Badge>
                {flag.experiments?.length ? (
                  <span className="text-xs text-muted">{flag.experiments.join(", ")}</span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-muted">{flag.detail}</p>
            </div>
          ))}
        </div>
      </Card>
      <LabelsAndSamples detail={data} />
    </div>
  );
}

export default function Phase1Page() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">正在加载预测实验...</div>}>
      <Phase1Content />
    </Suspense>
  );
}
